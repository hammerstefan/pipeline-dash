import asyncio
import collections
import http.client
import itertools
import logging
import os
import pathlib
import sys
import time
from typing import List, Optional

import mergedeep  # type: ignore
import rich_click as click
import yaml

import pipeline_dash.importer.utils as importer_utils
from pipeline_dash.importer.jenkins import collect_job_data, hash_url, JobName, recurse_downstream
from pipeline_dash.job_data import JobData, JobDataDict, JobStatus
from pipeline_dash.pipeline_config_schema import validate_pipeline_config
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
from pipeline_dash.viz.viz_rich import display_rich_table

logger = logging.getLogger("pipeline_dash")

click.rich_click.MAX_WIDTH = 120
verbose = False


def do_verbose():
    global verbose
    verbose = True
    http.client.HTTPConnection.debuglevel = 2
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)
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
                job_data[name].serial is None and serial is not None
                or serial is not None
                and job_data[name].serial is not None
                and float(job_data[name].serial or 0) < float(serial)
            ):
                status = [JobStatus.NOT_RUN.value]
                old_serial = True
            else:
                if job_data[name].status.value is None:
                    job_data[name].status = JobStatus.IN_PROGRESS
                status = [job_data[name].status.value]

            p["status"] = status[0]
            if statuses is None:
                statuses = []
            statuses.append(status)
        if isinstance(statuses, list) and isinstance(statuses[0], list):
            statuses = list(itertools.chain.from_iterable(statuses))
        if len(statuses) > 1:
            counter = collections.Counter(statuses[:-1])
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
        else:
            p["downstream_status"] = None

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
@click.argument("pipeline-config", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--recurse", is_flag=True, help="BETA: Recursively fetch job data for EVERY job listed")
@click.option("--verbose", is_flag=True, help="Show verbose output")
@click.option("--debug", is_flag=True, help="Turn on debug features (verbose logging, inspection features, etc)")
@click.option("--cli-report", is_flag=True, help="Generate a text-based report rather than graph visualization")
@click.option("--short-links", is_flag=True, help="Use hyperlinks instead of full jenkins links (may not work in all terminals)")
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
@click.option("--user-file", help="User file if server authentication is required", type=click.Path(exists=True))
def dash(pipeline_config, user_file, recurse, verbose, cli_report, short_links, cache, store, load, auth, debug):
    import diskcache  # type: ignore

    dcache = diskcache.Cache(".diskcache")
    if verbose:
        do_verbose()
    if store:
        os.makedirs(store, exist_ok=True)

    # noinspection PyPep8Naming
    PipelineConfigName = str
    user_config = yaml.safe_load(pathlib.Path(user_file).read_text()) if user_file else dict()

    job_configs = collections.OrderedDict()
    for path in (pathlib.Path(f) for f in pipeline_config):
        yaml_data = yaml.safe_load(path.read_text())
        rv = validate_pipeline_config(yaml_data)
        if not rv:
            logger.error(f"Failed to load pipeline config {path}.")
            continue
        jobs_config_name = yaml_data.get("name", path.name)
        yaml_data["path_hash"] = hash_url(str(path.absolute().resolve()))
        job_configs[jobs_config_name] = yaml_data

    if not len(job_configs):
        logger.error(f"No pipeline configs loaded. Exiting.")
        sys.exit(1)

    job_server_dicts: dict[PipelineConfigName, dict[JobName, str]] = dict()
    job_data: dict[PipelineConfigName, JobDataDict] = dict()
    pipeline_dicts: dict[PipelineConfigName, PipelineDict] = dict()
    # preload data
    os.makedirs(cache, exist_ok=True)
    for name, data in job_configs.items():
        start_time = time.process_time()
        job_server_dicts[name] = collect_jobs_dict(data)
        job_data[name] = asyncio.run(collect_job_data(job_server_dicts[name], load, store, user_config))
        pipeline_dicts[name] = collect_jobs_pipeline(data)
        if recurse:
            jobs_to_recurse = [
                p["name"] for p in find_all_pipeline(pipeline_dicts[name], lambda _, p: bool(p.get("recurse")))
            ]
            job_data_to_recurse = {k: v for k, v in job_data[name].items() if k in jobs_to_recurse}
            jobs_cache_file = pathlib.Path(cache, data["path_hash"])
            recurse_downstream(job_data_to_recurse, load, store, jobs_cache_file, user_config)
            job_data[name].update(job_data_to_recurse)
            job_server_dicts[name] = {name: data.server for name, data in job_data[name].items()}

        if recurse:
            pipeline_dicts[name] = add_recursive_jobs_pipeline(pipeline_dicts[name], job_data[name])
        importer_utils.add_human_url_to_job_data(job_data[name], data.get("url_translate", {}))
        calculate_status(pipeline_dicts[name], job_data[name])
        end_time = time.process_time()
        print(f"Loaded {name}, {len(job_data[name])} jobs in {end_time - start_time} sec")

    def get_job_data_(job_config_name: Optional[str] = None, refresh: bool = True) -> tuple[PipelineDict, JobDataDict]:
        pipeline_dict_ = pipeline_dicts[job_config_name]
        if refresh:
            start_time = time.process_time()
            job_data_: JobDataDict = asyncio.run(
                collect_job_data(job_server_dicts[job_config_name], load, store, user_config)
            )
            importer_utils.add_human_url_to_job_data(job_data_, job_configs[job_config_name].get("url_translate", {}))
            calculate_status(pipeline_dict_, job_data_)
            end_time = time.process_time()
            job_data[job_config_name] = job_data_
            print(f"Updated {job_config_name},  {len(job_data_)} jobs in {end_time - start_time} sec")
        else:
            job_data_ = job_data[job_config_name]

        return pipeline_dict_, job_data_

    # elements = generate_cyto_elements(pipeline_dict, job_data)
    # display_cyto(elements)
    if cli_report:
        display_rich_table(pipeline_dicts, job_data, load, store, short_links)
    else:
        display_dash(
            get_job_data_,
            viz_dash.Config(
                debug=debug,
                job_configs=list(job_configs.keys()),
            ),
        )


if __name__ == "__main__":
    cli()
