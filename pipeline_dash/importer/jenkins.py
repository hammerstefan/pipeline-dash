import asyncio
import base64
import hashlib
import json
import os
import pathlib
import pickle
from datetime import datetime
from typing import cast, Optional
from urllib.parse import urlparse, urlsplit

import aiohttp

from pipeline_dash.job_data import JobData, JobDataDict, JobStatus


def hash_url(url_or_path: str) -> str:
    file_name = base64.urlsafe_b64encode(url_or_path.encode())
    hash_ = hashlib.md5(file_name).hexdigest()
    return hash_


async def api(
    session: aiohttp.ClientSession,
    url: str,
    tree: str = "",
    depth: Optional[int] = None,
    load_dir: Optional[str] = None,
    store_dir: Optional[str] = None,
):
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
    # todo handle error
    try:
        json_data = json.loads(d)
    except json.decoder.JSONDecodeError:
        print(f"WARNING: Failed to get {api_url}")
        return {}
    if store_dir:
        possible_path = os.path.join(store_dir, file_name)
        with open(possible_path, "w") as f:
            json.dump(json_data, f)
    return json_data


async def get_job_data(
    session: aiohttp.ClientSession, server: str, job: str, load_dir: Optional[str], store_dir: Optional[str]
) -> JobData:
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
    name = r["name"]

    if not r["lastBuild"]:
        # there has not been a build
        return JobData(
            name=name,
            status=JobStatus.NOT_RUN,
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
    )
    return data


JobName = str
ServerUrl = str


async def collect_job_data(
    pipeline_jobs: dict[JobName, ServerUrl], load_dir: Optional[str], store_dir: Optional[str]
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
    async with aiohttp.ClientSession() as session:
        pipeline_promises = dict()
        for name, server in pipeline_jobs.items():
            fields_promise = get_job_data(session, server, name, load_dir, store_dir)
            pipeline_promises[name] = fields_promise

        result = await asyncio.gather(*pipeline_promises.values())

    return dict(zip(pipeline_jobs.keys(), result))


def recurse_downstream(
    job_data: JobDataDict, load: Optional[str], store: Optional[str], jobs_cache_file: pathlib.Path
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
            job_data2 = asyncio.run(collect_job_data(to_fetch, load, store))
            job_data.update(job_data2)
            to_fetch_cache = to_fetch.copy()
    to_fetch = get_to_fetch(job_data)
    to_fetch_cache.update(to_fetch)
    while to_fetch:
        job_data2 = asyncio.run(collect_job_data(to_fetch, load, store))
        job_data.update(job_data2)
        to_fetch = get_to_fetch(job_data2)
        to_fetch_cache.update(to_fetch)

    with open(jobs_cache_file, "wb") as fw:
        pickle.dump(to_fetch_cache, fw)
