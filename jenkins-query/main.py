import ast
import base64
import collections
import http.client
import itertools
import logging
import os
import pickle
import urllib.request
from typing import Union, Optional, Callable, Any, List

import requests
import browser_cookie3
from datetime import datetime, timedelta
from pprint import pprint

import click as click
import yaml
import rich.console
import rich.table
import rich.text
import json
from urllib.parse import urlparse, urlsplit
from bs4 import BeautifulSoup
import mergedeep
import asyncio
import aiohttp

from rich.progress import Progress

from cyto import generate_cyto_elements, display_cyto

verbose = False


def next_get(iterable, default):
    try:
        return next(iterable)
    except StopIteration:
        return default


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
    file_name = base64.urlsafe_b64encode(api_url.encode())
    if load_dir:
        possible_path = os.path.join(load_dir.encode(), file_name)
        if os.path.exists(possible_path):
            with open(possible_path, 'r') as f:
                return json.load(f)
    async with session.get(api_url) as req:
        d = await req.text()
    json_data = json.loads(d)
    if store_dir:
        possible_path = os.path.join(store_dir.encode(), file_name)
        with open(possible_path, 'w') as f:
            json.dump(json_data, f)
    return json_data


def authenticate(session: requests.Session, url: str, user_file: str) -> requests.Session:
    # Ubuntu SSO authentication hack
    # Should not be required anymore
    sess = session
    req = sess.get(url)
    if req.url == url or req.url == f"{url}/":
        return session
    req = sess.post(req.url, data={"openid_identifier": "login.ubuntu.com"})

    soup = BeautifulSoup(req.text, 'html.parser')
    s2 = soup.find(id="openid_message")
    url2 = s2.attrs["action"]
    data = {i.attrs["name"]: i.attrs["value"] for i in s2.find_all("input", attrs={"name": True})}
    req2 = sess.post(url2, data)
    if req2.url == url or req2.url == f"{url}/":
        return session
    soup = BeautifulSoup(req2.text, 'html.parser')
    s2 = soup.find("form", id="login-form")
    url = "https://" + urlparse(req2.url).netloc + s2.attrs["action"]
    data = {
        i.attrs["name"]: i.attrs["value"] if "value" in i.attrs else ""
        for i in s2.find_all("input", attrs={"name": True})
    }
    data2 = {}
    for key in ["csrfmiddlewaretoken", "user-intentions", "openid.usernamesecret"]:
        data2[key] = data[key]
    with open(user_file) as file:
        user_data = yaml.safe_load(file)
    data2["email"] = user_data["email"]
    data2["password"] = user_data["password"]
    data2["continue"] = ""
    req3 = sess.post(
        url,
        data2,
        headers={
            "Referer": url,
        },
    )
    token = input("2FA Token: ")
    data4 = {}
    soup = BeautifulSoup(req3.text, 'html.parser')
    s3 = soup.find("form", id="login-form")
    data = {
        i.attrs["name"]: i.attrs["value"] if "value" in i.attrs else ""
        for i in s3.find_all("input", attrs={"name": True})
    }
    for key in ["csrfmiddlewaretoken", "openid.usernamesecret"]:
        data4[key] = data[key]
    data4["continue"] = ""
    data4["oath_token"] = token
    req4 = sess.post(
        req3.url,
        data4,
        headers={
            "Referer": req3.url,
        },
    )

    if "device-verify" in req4.url:
        soup = BeautifulSoup(req4.text, 'html.parser')
        s4 = soup.find("form", id="login-form")
        data = {
            i.attrs["name"]: i.attrs["value"] if "value" in i.attrs else ""
            for i in s4.find_all("input", attrs={"name": True})
        }
        data5 = {}
        for key in ["csrfmiddlewaretoken", "openid.usernamesecret"]:
            data5[key] = data[key]
        data5["continue"] = ""
        req5 = sess.post(
            req4.url,
            data5,
            headers={
                "Referer": req4.url,
            },
        )
    return sess


def do_verbose():
    global verbose
    verbose = True
    http.client.HTTPConnection.debuglevel = 2
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def recurse_pipeline(pipeline: Union[dict, list],
                     fn: Callable[[str, Union[dict, list], ...], Any],
                     *args,
                     **kwargs):
    rets = []
    if isinstance(pipeline, dict):
        for k, v in pipeline.items():
            if k.startswith("__") and k.endswith("__"):
                continue
            ret = fn(k, v, *args, **kwargs)
            if ret is not None:
                rets.append(ret)
    elif isinstance(pipeline, list):
        for k in pipeline:
            if type(k) is dict:
                _name = next(iter(k))
            else:
                _name = k
            if _name.startswith("__") and _name.endswith("__"):
                continue
            ret = fn(_name, [], *args, **kwargs)
            if ret is not None:
                rets.append(ret)
    return rets if rets else None



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
        recurse_pipeline(pipeline, fill_pipeline, server, p)
        if not name.startswith("."):
            p["__server__"] = server
        else:
            name = name[1:]
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
    return struct


def init_session(session, servers, user_file):
    if os.path.exists(".cookies"):
        with open(".cookies", "rb") as f:
            session.cookies.update(pickle.load(f))
    for server in servers:
        authenticate(session, server, user_file)


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
    parameters = next(a["parameters"] for a in r["actions"] if a["_class"] == "hudson.model.ParametersAction")
    data = {
        "name": name,
        "build_num": r["id"],
        "status": r["result"],
        "timestamp": datetime.utcfromtimestamp(r["timestamp"]/1000.0),
        "serial": next_get((p["value"] for p in parameters if p["name"] == "SERIAL"), None),
        "url": url.geturl(),
    }
    return data


def add_jobs_to_table(name: str,
                      job_struct: dict,
                      job_data: dict,
                      prefix: str,
                      table: rich.table.Table,
                      progress_task_fn: Callable,
                      load_dir: Optional[str],
                      store_dir: Optional[str],
                      ):
    def status(str):
        if str is None:
            str = "In Progress"
        text = rich.text.Text(str)
        if str == "SUCCESS":
            text.stylize("green")
        elif str == "UNSTABLE":
            text.stylize("bold orange")
        elif str == "In Progress":
            text.stylize("yellow")
        elif str == "FAILURE":
            text.stylize("bold red3")
        return text


    def add_prefix(prefix: str) -> str:
        if not len(prefix):
            prefix = "|-"
        else:
            prefix = f" {prefix}"
        return prefix

    def remove_prefix(prefix: str) -> str:
        if prefix == "|-":
            prefix = ""
        elif len(prefix):
            prefix = prefix[1:]
        return prefix

    if "__server__" in job_struct:
        fields = job_data[name]
        table.add_row(
            prefix + fields["name"],
            fields["serial"],
            fields["build_num"],
            fields["timestamp"].strftime("%y-%m-%d %H:%M UTC") if fields["timestamp"] else None ,
            status(fields["status"]),
            fields["url"],
            )
        if fields["timestamp"] and datetime.now() - fields["timestamp"] > timedelta(hours=24):
            table.rows[-1].style = "dim"
        progress_task_fn()
    else:
        table.add_row(prefix + name, style="bold")

    for next_name in job_struct:
        if next_name == "__server__":
            continue
        prefix = add_prefix(prefix)
        add_jobs_to_table(
            name=next_name,
            job_struct=job_struct[next_name],
            job_data=job_data,
            prefix=prefix,
            table=table,
            progress_task_fn=progress_task_fn,
            load_dir=load_dir,
            store_dir=store_dir,
        )
        prefix = remove_prefix(prefix)


def count_dict(d):
    return sum([count_dict(v) if isinstance(v, dict) else 1 for v in d.values()])


async def collect_job_data(yaml_data: dict, load_dir, store_dir) -> dict:
    pipeline_jobs = collect_jobs_dict(yaml_data)

    # session = requests.Session()
    async with aiohttp.ClientSession() as session:
    # if auth:
    #     init_session(
    #         session,
    #         (s for s in yaml_data["servers"] if yaml_data["servers"][s]["authenticate"]),
    #         user_file,
    #     )

        pipeline_promises = dict()
        for name, server in pipeline_jobs.items():
            fields_promise = get_job_data(session, server, name, load_dir, store_dir)
            pipeline_promises[name] = fields_promise

        result = await asyncio.gather(*pipeline_promises.values())

    # with open(".cookies", "wb") as f:
    #     pickle.dump(session.cookies, f)

    return dict(zip(pipeline_jobs.keys(), result))


def calculate_status(pipeline: dict, job_data: dict):
    def recursive_calculate_status(name: str, p: dict) -> List[str]:
        statuses = recurse_pipeline(p, recursive_calculate_status)
        if "__server__" in p:
            status = job_data[name]["status"]
            if status is None:
                status = "NOT RUN"
            if statuses is None:
                statuses = []
            statuses.append(status)
        if isinstance(statuses, list) and isinstance(statuses[0], list):
            statuses = list(itertools.chain.from_iterable(statuses))
        if statuses:
            counter = collections.Counter(statuses)
            if counter["FAILURE"]:
                p["__status__"] = "FAILURE"
            elif counter["UNSTABLE"]:
                p["__status__"] = "UNSTABLE"
            elif counter["In Progress"]:
                p["__status__"] = "In Progress"
            elif counter["SUCCESS"]:
                p["__status__"] = "SUCCESS"
            else:
                p["__status__"] = "NOT RUN"

        return statuses

    s = recursive_calculate_status("", pipeline)
    print(s)



@click.command()
@click.argument("jobs_file")
@click.option("--user-file", help="User file if server authentication is required")
@click.option("--verbose", default=False)
@click.option("--store", help="Directory to store Jenkins JSON data")
@click.option("--load", help="Directory to load Jenkins JSON data")
@click.option("--auth/--no-auth", default=True, help="Perform login.ubuntu.com SSO authentication")
def main(jobs_file, user_file, verbose, store, load, auth):
    if verbose:
        do_verbose()
    if store:
        os.makedirs(store, exist_ok=True)

    with open(jobs_file) as file:
        yaml_data = yaml.safe_load(file)
    pipeline_dict = collect_jobs_pipeline(yaml_data)
    job_data = asyncio.run(collect_job_data(yaml_data, load, store))
    calculate_status(pipeline_dict, job_data)



    # console = rich.console.Console()
    # other_table = rich.table.Table(title="Other Jobs")
    # other_table.add_column("Name")
    # other_table.add_column("Serial")
    # other_table.add_column("No.")
    # other_table.add_column("Time")
    # other_table.add_column("Status")
    # other_table.add_column("URL")
    # with Progress(transient=True) as progress:
    #     task = progress.add_task("Fetching data...", total=count_dict(pipeline_dict))
    #     progress_fn = lambda: progress.advance(task)
    #     for name, data in pipeline_dict.items():
    #         add_jobs_to_table(
    #             name=name,
    #             job_struct=data,
    #             job_data=job_data,
    #             prefix="",
    #             table=other_table,
    #             progress_task_fn=progress_fn,
    #             load_dir=load,
    #             store_dir=store,
    #         )
    #
    # console.print(other_table)

    elements = generate_cyto_elements(pipeline_dict, job_data)
    display_cyto(elements)


    print()


if __name__ == '__main__':
   main()

