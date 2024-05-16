from datetime import datetime, timedelta
from typing import Callable, Optional
from pipeline_dash.job_data import JobStatus

import rich.console
import rich.table
import rich.text
from rich.progress import Progress


def add_jobs_to_table(
    name: str,
    job_struct: dict,
    job_data: dict,
    prefix: str,
    table: rich.table.Table,
    progress_task_fn: Callable,
    load_dir: Optional[str],
    store_dir: Optional[str],
    short_links: bool
):
    def status(job_status: JobStatus):
        if job_status is JobStatus.UNDEFINED:
            job_status = JobStatus.IN_PROGRESS
        text = rich.text.Text(job_status.value)
        if job_status == JobStatus.SUCCESS:
            text.stylize("green")
        elif job_status == JobStatus.UNSTABLE:
            text.stylize("bold orange")
        elif job_status == JobStatus.IN_PROGRESS:
            text.stylize("yellow")
        elif job_status == JobStatus.FAILURE:
            text.stylize("bold red3")
        return text

    def link(name: str, url: str):
        return f'[link={url}]{name}[/link]'

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

    if "server" in job_struct:
        fields = job_data[name]
        table.add_row(
            prefix + fields.name,
            fields.serial,
            fields.build_num,
            fields.timestamp.strftime("%y-%m-%d %H:%M UTC") if fields.timestamp else None,
            status(fields.status),
            link("Jenkins Link", fields.url) if short_links else fields.url
        )
        if fields.timestamp and datetime.now() - fields.timestamp > timedelta(hours=24):
            table.rows[-1].style = "dim"
        progress_task_fn()
    else:
        table.add_row(prefix + name, style="bold")

    for next_name in job_struct['children']:
        prefix = add_prefix(prefix)
        add_jobs_to_table(
            name=next_name,
            job_struct=job_struct['children'][next_name],
            job_data=job_data,
            prefix=prefix,
            table=table,
            progress_task_fn=progress_task_fn,
            load_dir=load_dir,
            store_dir=store_dir,
            short_links=short_links,
        )
        prefix = remove_prefix(prefix)


def count_dict(d):
    return sum([count_dict(v) if isinstance(v, dict) else 1 for v in d.values()])


def display_rich_table(pipeline_dict, job_data, load, store, short_links):
    console = rich.console.Console()
    other_table = rich.table.Table(title="Jobs")
    other_table.add_column("Name")
    other_table.add_column("Serial")
    other_table.add_column("No.")
    other_table.add_column("Time")
    other_table.add_column("Status")
    other_table.add_column("URL")
    with Progress(transient=True) as progress:
        task = progress.add_task("Fetching data...", total=count_dict(pipeline_dict))
        progress_fn = lambda: progress.advance(task)
        for name, data in pipeline_dict.items():
            add_jobs_to_table(
                name=name,
                job_struct=data,
                job_data=job_data[name],
                prefix="",
                table=other_table,
                progress_task_fn=progress_fn,
                load_dir=load,
                store_dir=store,
                short_links=short_links
            )
    console.print(other_table)
