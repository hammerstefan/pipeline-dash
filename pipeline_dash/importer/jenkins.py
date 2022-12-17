import asyncio
import base64
import hashlib
import json
import logging
import os
import pathlib
import pickle
from datetime import datetime
from pprint import pformat
from textwrap import indent
from typing import Callable, cast, Optional
from urllib.parse import urlparse, urlsplit

import aiohttp
import tenacity
from tenacity import retry, RetryCallState, RetryError, stop_after_delay, wait_random_exponential

from pipeline_dash.job_data import JobData, JobDataDict, JobStatus

logger = logging.getLogger(__name__)


def hash_url(url_or_path: str) -> str:
    file_name = base64.urlsafe_b64encode(url_or_path.encode())
    hash_ = hashlib.md5(file_name).hexdigest()
    return hash_


def _cb_api_failure(retry_state: RetryCallState) -> dict:
    """tenacity.retry callback on `api() failure"""

    def format_output(outcome: Optional[tenacity.Future]):
        tab = "\t"
        return f"Exception: {outcome.exception() if outcome else 'UNKNOWN'}\n" + indent(
            f"Function: {retry_state.fn.__name__ if retry_state.fn else 'UNKNWON'}\n"
            f"Args:\n{indent(pformat(retry_state.args, width=200), tab)}\n"
            f"Kwargs:\n{indent(pformat(retry_state.kwargs, width=200), tab)}\n",
            "\t",
        )

    url = retry_state.kwargs.get("url") or retry_state.args[1]
    logger.warning(f"Failed to get API at {url}")
    if retry_state.outcome is None:
        logger.debug(format_output(retry_state.outcome))
        raise RuntimeError("Tenacity retry failed but no Future available (this should not happen")

    logger.debug(format_output(retry_state.outcome))
    ex = retry_state.outcome.exception()
    match ex:
        case json.decoder.JSONDecodeError():
            return {}
        case _:
            raise RetryError(retry_state.outcome) from ex


def log_retry(
    log_level: int,
    sec_format: str = "%0.2f",
) -> Callable[["RetryCallState"], None]:
    def fn(retry_state: RetryCallState) -> None:
        url = retry_state.kwargs.get("url") or retry_state.args[1]
        logger.log(
            log_level,
            f"Failed '{__name__}.{retry_state.fn and retry_state.fn.__qualname__}' for url '{url}' "
            f"after {sec_format % retry_state.seconds_since_start}(s), "
            f"this was attempt {retry_state.attempt_number}.",
        )

    return fn


@retry(
    wait=wait_random_exponential(multiplier=0.5, max=10),
    stop=stop_after_delay(10),
    # before=before_log(logger, logging.DEBUG),
    after=log_retry(logging.INFO),
    retry_error_callback=_cb_api_failure,
)
async def api(
    session: aiohttp.ClientSession,
    url: str,
    tree: str = "",
    depth: Optional[int] = None,
    load_dir: Optional[str] = None,
    store_dir: Optional[str] = None,
) -> dict:
    api_url = f"{url}/api/json"
    q = "?"
    if tree:
        api_url += f"{q}tree={tree}"
        q = "?"
    if depth:
        api_url += f"{q}depth={depth}"
        q = "?"
    file_name = hash_url(api_url)
    if load_dir:
        possible_path = os.path.join(load_dir, file_name)
        if os.path.exists(possible_path):
            with open(possible_path, "r") as f:
                return json.load(f)
    async with session.get(api_url) as req:
        d = await req.text()
    # todo handle error better than throwing JSONDecodeError here if failed to get job API
    json_data = json.loads(d)
    if store_dir:
        possible_path = os.path.join(store_dir, file_name)
        with open(possible_path, "w") as f:
            json.dump(json_data, f)
    return json_data


async def get_job_data(
    session: aiohttp.ClientSession,
    server: str,
    job: str,
    load_dir: Optional[str],
    store_dir: Optional[str],
) -> Optional[JobData]:
    """
    Get data for a single Jenkins `job` from the `server` url
    :param session: aiohttp.ClientSession to use for requests
    :param server: Base URL of the Jenkins Server
    :param job: Job name for which to get data
    :param load_dir: Local directory path str from which to load cached Jenkins data (can be used to run this
    function without an internet connection to `server`)
    :param store_dir: Local directory path str where to store cached Jenkins data (can be used to run this
    function without an internet connection to `server`). Can later be used as the `load_dir` param of this function.
    :return: JobData dataclass containing job data
    """
    server_url = urlparse(server)
    r = await api(
        session,
        f"{server}/job/{job}",
        tree="name,lastBuild[url],downstreamProjects[name,url]",
        load_dir=load_dir,
        store_dir=store_dir,
    )
    if not r:
        return None
    name = r["name"]

    if not r["lastBuild"]:
        # there has not been a build
        return JobData(
            name=name,
            status=JobStatus.NOT_RUN,
            server=server,
        )
    downstream = {i["name"]: server for i in r["downstreamProjects"]}
    # update base netloc of url to use that of the job config's server address, to avoid problems with SSO
    url = urlsplit(r["lastBuild"]["url"])
    url = url._replace(netloc=server_url.netloc)

    r = await api(
        session,
        cast(str, url.geturl()),
        tree="id,result,timestamp,actions[parameters[name,value]]",
        load_dir=load_dir,
        store_dir=store_dir,
    )
    if not r:
        return JobData(
            name=name,
            status=JobStatus.UNDEFINED,
            server=server,
        )
    parameters: list = next(
        (a["parameters"] for a in r["actions"] if a and a["_class"] == "hudson.model.ParametersAction"), []
    )
    data = JobData(
        name=name,
        build_num=r["id"],
        status=JobStatus(r["result"]),
        timestamp=datetime.utcfromtimestamp(r["timestamp"] / 1000.0),
        serial=next((p["value"] for p in parameters if p["name"] == "SERIAL"), None),
        url=url.geturl(),
        downstream=downstream,
        server=server,
    )
    return data


JobName = str
ServerUrl = str


async def collect_job_data(
    pipeline_jobs: dict[JobName, ServerUrl],
    load_dir: Optional[str],
    store_dir: Optional[str],
    user_config: Optional[dict],
) -> JobDataDict:
    """
    Get dict of all job data
    :param pipeline_jobs:
    :param load_dir: Local directory path str from which to load cached Jenkins data (can be used to run this
    function without an internet connection to `server`)
    :param store_dir: Local directory path str where to store cached Jenkins data (can be used to run this
    function without an internet connection to `server`). Can later be used as the `load_dir` param of this function.
    :return: Dictionary containing all JobData for every entry in `pipeline_jobs`
    """
    auth = (
        aiohttp.BasicAuth(login=user_config["user"], password=user_config["token"])
        if user_config and {"user", "token"} <= user_config.keys()
        else None
    )
    async with aiohttp.ClientSession(auth=auth) as session:
        pipeline_promises = dict()
        for name, server in pipeline_jobs.items():
            fields_promise = get_job_data(session, server, name, load_dir, store_dir)
            pipeline_promises[name] = fields_promise

        result = await asyncio.gather(*pipeline_promises.values())

    return dict(zip(pipeline_jobs.keys(), result))


def recurse_downstream(
    job_data: JobDataDict,
    load: Optional[str],
    store: Optional[str],
    jobs_cache_file: pathlib.Path,
    user_config: Optional[dict],
) -> None:
    """
    Recurse through `job_data` dict and fetch `JobData` for every listed "downstream" and add it to `job_data` dict
    :param job_data: Dict of job data
    :param load: Local directory path str from which to load cached Jenkins data (can be used to run this
    function without an internet connection to `server`)
    :param store: Local directory path str where to store cached Jenkins data (can be used to run this
    function without an internet connection to `server`). Can later be used as the `load_dir` param of this function
    :param jobs_cache_file:
    """

    def get_to_fetch(job_data_: JobDataDict) -> dict[JobName, ServerUrl]:
        to_fetch_ = dict()
        for k, v in job_data_.items():
            for name in v.downstream:
                if name not in job_data_:
                    to_fetch_[name] = v.downstream[name]
        return to_fetch_

    to_fetch_cache = dict()
    if jobs_cache_file.exists():
        with open(jobs_cache_file, "rb") as fr:
            to_fetch = pickle.load(fr)
            job_data2 = asyncio.run(collect_job_data(to_fetch, load, store, user_config))
            job_data.update(job_data2)
            to_fetch_cache = to_fetch.copy()
    to_fetch = get_to_fetch(job_data)
    to_fetch_cache.update(to_fetch)
    while to_fetch:
        job_data2 = asyncio.run(collect_job_data(to_fetch, load, store, user_config))
        job_data.update(job_data2)
        to_fetch = get_to_fetch(job_data2)
        to_fetch_cache.update(to_fetch)

    with open(jobs_cache_file, "wb") as fw:
        pickle.dump(to_fetch_cache, fw)
