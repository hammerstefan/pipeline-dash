import base64
import collections
import hashlib
import http.client
import itertools
import logging
import os
import pathlib
import pickle
import time
import uuid
from typing import Union, Optional, List

from datetime import datetime

import click as click
import yaml
import json
from urllib.parse import urlparse, urlsplit
import mergedeep
import asyncio
import aiohttp

from pipeline_utils import recurse_pipeline
from viz.dash.viz_dash import display_dash

verbose = False


def next_get(iterable, default):
    try:
        return next(iterable)
    except StopIteration:
        return default


def hash_url(url_or_path: str) -> str:
    file_name = base64.urlsafe_b64encode(url_or_path.encode())
    hash_ = hashlib.md5(file_name).hexdigest()
    return hash_


async def api(session: aiohttp.ClientSession,
              url: str,
              tree: str = "",
              depth: int = None,
              load_dir: Optional[str] = None,
              store_dir: Optional[str] = None,
              ):
    api_url = f"{url}/api/json"
    q="?"
    if tree:
        api_url += f"{q}tree={tree}"
        q="?"
    if depth:
        api_url += f"{q}depth={depth}"
        q = "?"
    file_name = hash_url(api_url)
    if load_dir:
        possible_path = os.path.join(load_dir, file_name)
        if os.path.exists(possible_path):
            with open(possible_path, 'r') as f:
                return json.load(f)
    async with session.get(api_url) as req:
        d = await req.text()
    json_data = json.loads(d)
    if store_dir:
        possible_path = os.path.join(store_dir, file_name)
        with open(possible_path, 'w') as f:
            json.dump(json_data, f)
    return json_data


def do_verbose():
    global verbose
    verbose = True
    http.client.HTTPConnection.debuglevel = 2
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def collect_jobs_dict(yaml_data: dict) -> dict:
    def fill_pipeline(name: str, pipeline: Union[dict, list], server: str, out_struct: dict):
        recurse_pipeline(pipeline, fill_pipeline, server, out_struct)
        if not name.startswith("."):
            out_struct[name] = server


    struct = collections.OrderedDict()
    for server, data in yaml_data["servers"].items():
        for k in data["pipelines"]:
            if type(data["pipelines"]) is dict:
                fill_pipeline(k, data["pipelines"][k], server, struct)
            else:
                fill_pipeline(k, [], server, struct)
    return struct


def collect_jobs_pipeline(yaml_data: dict) -> dict:
    def fill_pipeline(name: str, pipeline: Union[dict, list], server: str, out_struct: dict):
        p = {}
        recurse = pipeline["recurse"] if "recurse" in pipeline else False
        recurse_pipeline(pipeline, fill_pipeline, server, p)
        if name and not name.startswith("."):
            p["__server__"] = server
            if recurse:
                p["__recurse__"] = recurse
        else:
            name = name[1:]
        p["__uuid__"] = str(uuid.uuid4())
        out_struct[name] = p

    struct = collections.OrderedDict()
    for server, data in yaml_data["servers"].items():
        tmp = {}
        for k in data["pipelines"]:
            if type(data["pipelines"]) is dict:
                fill_pipeline(k, data["pipelines"][k], server, tmp)
            else:
                fill_pipeline(k, [], server, tmp)
        mergedeep.merge(struct, tmp, strategy=mergedeep.Strategy.TYPESAFE_ADDITIVE)
    struct["__uuid__"] = str(uuid.uuid4())
    return struct


async def get_job_data(session, server, job, load_dir, store_dir):
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
        return {
            "name": name,
            "build_num": None,
            "status": "NOT RUN",
            "timestamp": None,
            "serial": None,
            "url": None,
        }
    downstream = {i["name"]: server for i in r["downstreamProjects"]}
    # update base netloc of url to use that of the job config's server address, to avoid problems with SSO
    url = urlsplit(r["lastBuild"]["url"])
    url = url._replace(netloc=server_url.netloc)

    r = await api(
        session,
        url.geturl(),
        tree="id,result,timestamp,actions[parameters[name,value]]",
        load_dir=load_dir,
        store_dir=store_dir,
    )
    parameters = next_get((a["parameters"] for a in r["actions"] if a and a["_class"] == "hudson.model.ParametersAction"), [])
    data = {
        "name": name,
        "build_num": r["id"],
        "status": r["result"],
        "timestamp": datetime.utcfromtimestamp(r["timestamp"]/1000.0),
        "serial": next_get((p["value"] for p in parameters if p["name"] == "SERIAL"), None),
        "url": url.geturl(),
        "downstream": downstream,
    }
    return data


async def collect_job_data(pipeline_jobs: dict, load_dir, store_dir) -> dict:
    async with aiohttp.ClientSession() as session:

        pipeline_promises = dict()
        for name, server in pipeline_jobs.items():
            fields_promise = get_job_data(session, server, name, load_dir, store_dir)
            pipeline_promises[name] = fields_promise

        result = await asyncio.gather(*pipeline_promises.values())

    return dict(zip(pipeline_jobs.keys(), result))


def calculate_status(pipeline: dict, job_data: dict):
    def recursive_calculate_status(name: str, p: dict, serial=None) -> List[str]:
        if serial is None:
            serial = job_data.get(name, dict()).get("serial", None)
        statuses = recurse_pipeline(p, recursive_calculate_status, serial)
        old_serial = False
        if "__server__" in p:
            if serial is not None \
                    and job_data[name].get("serial", "0") is not None \
                    and float(job_data[name].get("serial", "0")) < float(serial):
                status = ["NOT RUN"]
                old_serial = True
            else:
                status = [job_data[name]["status"]]
            p["__status__"] = status[0]
            if statuses is None:
                statuses = []
            statuses.append(status)
        if isinstance(statuses, list) and isinstance(statuses[0], list):
            statuses = list(itertools.chain.from_iterable(statuses))
        if statuses:
            counter = collections.Counter(statuses)
            if old_serial:
                p["__downstream_status__"] = "NOT RUN"
            elif counter["FAILURE"]:
                p["__downstream_status__"] = "FAILURE"
            elif counter["UNSTABLE"]:
                p["__downstream_status__"] = "UNSTABLE"
            elif counter["In Progress"] or counter[None]:
                p["__downstream_status__"] = "In Progress"
            elif counter["SUCCESS"]:
                p["__downstream_status__"] = "SUCCESS"
            else:
                p["__downstream_status__"] = "NOT RUN"

        return statuses

    s = recursive_calculate_status("", pipeline)


def add_recursive_jobs_pipeline(pipeline: dict, job_data: dict) -> dict:
    def fill_pipeline(name: str, pipeline: Union[dict, list]):
        if "__server__" in pipeline and name in job_data and "downstream" in job_data[name]:
            server = pipeline["__server__"]
            for k, v in job_data[name]["downstream"].items():
                pipeline[k] = {
                    "__server__": v
                }
        pipeline.setdefault("__uuid__", str(uuid.uuid4()))
        recurse_pipeline(pipeline, fill_pipeline)

    fill_pipeline("", pipeline)
    return pipeline


def recurse_downstream(job_data: dict, load: str, store: str, jobs_cache_file: pathlib.Path):
    def get_to_fetch(job_data_: dict) -> dict:
        to_fetch_ = dict()
        for k, v in job_data_.items():
            for name in v.get("downstream", []):
                if name not in job_data_:
                    to_fetch_[name] = v["downstream"][name]
        return to_fetch_

    to_fetch_cache = dict()
    if jobs_cache_file.exists():
        with open(jobs_cache_file, "rb") as f:
            to_fetch = pickle.load(f)
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

    with open(jobs_cache_file, "wb") as f:
        pickle.dump(to_fetch_cache, f)


@click.group()
def cli():
    pass


@cli.command()
@click.argument("jobs_file_in")
@click.option("--verbose", default=False)
@click.option("--cache", help="Directory to cache data", default=f"{pathlib.Path(__file__).parent.resolve()}/.cache")
@click.option("--store", help="Directory to store Jenkins JSON data")
@click.option("--load", help="Directory to load Jenkins JSON data")
def recurse(jobs_file_in, verbose, cache, store, load):
    if verbose:
        do_verbose()
    if store:
        os.makedirs(store, exist_ok=True)
    start_time = time.process_time()
    with open(jobs_file_in) as file:
        yaml_data = yaml.safe_load(file)
    job_data = asyncio.run(collect_job_data(collect_jobs_dict(yaml_data), load, store))
    hash_ = hash_url(str(pathlib.Path(jobs_file_in).absolute().resolve()))
    os.makedirs(cache, exist_ok=True)
    jobs_cache_file = pathlib.Path(cache, hash_)
    recurse_downstream(job_data, load, store, jobs_cache_file)

    pipeline_dict = collect_jobs_pipeline(yaml_data)
    pipeline_dict = add_recursive_jobs_pipeline(pipeline_dict, job_data)
    calculate_status(pipeline_dict, job_data)
    end_time = time.process_time()
    print(f"Loaded {len(job_data)} jobs in {end_time-start_time} sec")

    # display_rich_table(pipeline_dict, job_data, load, store)
    # elements = generate_cyto_elements(pipeline_dict, job_data)
    # display_cyto(elements)
    display_dash(pipeline_dict, job_data)


@cli.command()
@click.argument("jobs_file")
@click.option("--user-file", help="User file if server authentication is required")
@click.option("--recurse", is_flag=True, help="Recursively fetch job data", default=False)
@click.option("--verbose", default=False)
@click.option("--cache", help="Directory to cache data", default=f"{pathlib.Path(__file__).parent.resolve()}/.cache")
@click.option("--store", help="Directory to store Jenkins JSON data")
@click.option("--load", help="Directory to load Jenkins JSON data")
@click.option("--auth/--no-auth", default=True, help="Perform login.ubuntu.com SSO authentication")
def main(jobs_file, user_file, recurse, verbose, cache, store, load, auth):
    if verbose:
        do_verbose()
    if store:
        os.makedirs(store, exist_ok=True)
    start_time = time.process_time()
    with open(jobs_file) as file:
        yaml_data = yaml.safe_load(file)
    job_data = asyncio.run(collect_job_data(collect_jobs_dict(yaml_data), load, store))
    hash_ = hash_url(str(pathlib.Path(jobs_file).absolute().resolve()))
    os.makedirs(cache, exist_ok=True)
    if recurse:
        jobs_cache_file = pathlib.Path(cache, hash_)
        recurse_downstream(job_data, load, store, jobs_cache_file)

    pipeline_dict = collect_jobs_pipeline(yaml_data)
    if recurse:
        pipeline_dict = add_recursive_jobs_pipeline(pipeline_dict, job_data)
    calculate_status(pipeline_dict, job_data)
    end_time = time.process_time()
    print(f"Loaded {len(job_data)} jobs in {end_time-start_time} sec")

    # display_rich_table(pipeline_dict, job_data, load, store)
    # elements = generate_cyto_elements(pipeline_dict, job_data)
    # display_cyto(elements)
    display_dash(pipeline_dict, job_data)


if __name__ == '__main__':
   cli()

