import asyncio
import collections
import http.client
import itertools
import logging
import os
import pathlib
import time
from typing import List, Optional

import mergedeep  # type: ignore
import rich_click as click
import yaml

from pipeline_dash.importer.jenkins import collect_job_data, hash_url, JobName, recurse_downstream
from pipeline_dash.job_data import JobData, JobDataDict, JobStatus
from pipeline_dash.pipeline_utils import (
    add_recursive_jobs_pipeline,
    collect_jobs_dict,
    collect_jobs_pipeline,
    find_all_pipeline,
    PipelineDict,
    recurse_pipeline,
)
from pipeline_dash.viz.dash import viz_dash
from pipeline_dash.viz.dash.viz_dash import display_dash

click.rich_click.MAX_WIDTH = 120
verbose = False


def do_verbose():
    global verbose
    verbose = True
    http.client.HTTPConnection.debuglevel = 2
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def calculate_status(pipeline: PipelineDict, job_data: JobDataDict) -> None:
    """
    Add "status" and "downstream_status" values to each `pipeline` entry recursively.
    :param pipeline: `PipelineDict` pipeline to update
    :param job_data: Job data dict that whill be used to calculate "status" and "downstream_statu"
    """

    def recursive_calculate_status(name: JobName, p: PipelineDict, serial: Optional[str] = None) -> List[str]:
        if serial is None:
            serial = job_data.get(name, JobData.UNDEFINED).serial
        statuses = recurse_pipeline(p, recursive_calculate_status, serial)
        old_serial = False
        if "server" in p:
            if (
                serial is not None
                and job_data[name].serial is not None
                and float(job_data[name].serial or 0) < float(serial)
            ):
                status = [JobStatus.NOT_RUN.value]
                old_serial = True
            else:
                status = [job_data[name].status.value]
            p["status"] = status[0]
            if statuses is None:
                statuses = []
            statuses.append(status)
        if isinstance(statuses, list) and isinstance(statuses[0], list):
            statuses = list(itertools.chain.from_iterable(statuses))
        if statuses:
            counter = collections.Counter(statuses)
            if old_serial:
                p["downstream_status"] = "NOT RUN"
            elif counter["FAILURE"]:
                p["downstream_status"] = "FAILURE"
            elif counter["UNSTABLE"]:
                p["downstream_status"] = "UNSTABLE"
            elif counter["In Progress"] or counter[None]:
                p["downstream_status"] = "In Progress"
            elif counter["SUCCESS"]:
                p["downstream_status"] = "SUCCESS"
            else:
                p["downstream_status"] = "NOT RUN"

        return statuses

    s = recursive_calculate_status("", pipeline)


@click.group()
def cli():
    pass


# noinspection PyShadowingBuiltins
@cli.command()
@click.argument("subcommand", required=False)
@click.pass_context
def help(ctx, subcommand):
    if sc := cli.get_command(ctx, subcommand):
        click.echo(sc.get_help(ctx))
    else:
        click.echo(cli.get_help(ctx))


@cli.command()
@click.argument("jobs_file", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--recurse", is_flag=True, help="BETA: Recursively fetch job data for EVERY job listed")
@click.option("--verbose", is_flag=True, help="Show verbose output")
@click.option("--debug", is_flag=True, help="Turn on debug features (verbose logging, inspection features, etc)")
@click.option(
    "--cache",
    help="Directory to cache data",
    default=f"{pathlib.Path(__file__).parent.resolve()}/.cache",
    show_default=True,
)
@click.option("--store", help="EXPERIMENTAL: Directory to store Jenkins JSON data")
@click.option("--load", help="EXPERIMENTAL: Directory to load Jenkins JSON data")
@click.option(
    "--auth/--no-auth",
    default=False,
    help="EXPERIMENTAL: Perform login.ubuntu.com SSO authentication",
    show_default=True,
)
@click.option("--user-file", help="User file if server authentication is required")
def dash(jobs_file, user_file, recurse, verbose, cache, store, load, auth, debug):
    if verbose:
        do_verbose()
    if store:
        os.makedirs(store, exist_ok=True)

    job_configs = collections.OrderedDict()
    for path in (pathlib.Path(f) for f in jobs_file):
        yaml_data = yaml.safe_load(path.read_text())
        jobs_config_name = yaml_data.get("name", path.name)
        job_configs[jobs_config_name] = yaml_data

    def get_job_data_(job_config_name: Optional[str] = None) -> tuple[PipelineDict, JobDataDict]:
        yaml_data_ = job_configs[job_config_name] if job_config_name else next(iter(job_configs.values()))
        start_time = time.process_time()
        job_data_: JobDataDict = asyncio.run(collect_job_data(collect_jobs_dict(yaml_data_), load, store))
        hash_ = hash_url(str(pathlib.Path(jobs_file[0]).absolute().resolve()))
        os.makedirs(cache, exist_ok=True)
        pipeline_dict_ = collect_jobs_pipeline(yaml_data_)
        if recurse:
            jobs_to_recurse = [
                p["name"] for p in find_all_pipeline(pipeline_dict_, lambda name, p: bool(p.get("recurse")))
            ]
            job_data_to_recurse = {k: v for k, v in job_data_.items() if k in jobs_to_recurse}
            jobs_cache_file = pathlib.Path(cache, hash_)
            recurse_downstream(job_data_to_recurse, load, store, jobs_cache_file)
            job_data_.update(job_data_to_recurse)

        if recurse:
            pipeline_dict_ = add_recursive_jobs_pipeline(pipeline_dict_, job_data_)
        calculate_status(pipeline_dict_, job_data_)
        end_time = time.process_time()
        print(f"Loaded {len(job_data_)} jobs in {end_time - start_time} sec")
        return pipeline_dict_, job_data_

    # display_rich_table(pipeline_dict, job_data, load, store)
    # elements = generate_cyto_elements(pipeline_dict, job_data)
    # display_cyto(elements)
    display_dash(get_job_data_, viz_dash.Config(debug=debug, job_configs=list(job_configs.keys())))


if __name__ == "__main__":
    cli()
