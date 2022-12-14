from __future__ import annotations

import collections
import itertools
import uuid
from typing import Any, Callable, Concatenate, ParamSpec, TypedDict, Union

import mergedeep  # type: ignore
from typing_extensions import NotRequired

from pipeline_dash.job_data import JobData, JobDataDict, JobName
from pipeline_dash.utils import timeit


class PipelineDict(TypedDict):
    name: str
    children: dict[str, PipelineDict]
    uuid: str
    server: NotRequired[str]
    recurse: NotRequired[bool]
    status: NotRequired[str]
    downstream_status: NotRequired[str]
    label: NotRequired[str]


P = ParamSpec("P")

special_keys = [
    "$label",
    "$recurse",
]


def recurse_yaml(
    pipeline: list | dict, fn: Callable[Concatenate[str, dict | list, P], Any], *args: P.args, **kwargs: P.kwargs
):
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


def recurse_pipeline(
    pipeline: PipelineDict, fn: Callable[Concatenate[str, PipelineDict, P], Any], *args: P.args, **kwargs: P.kwargs
):
    # todo FIXME this is not correct, still parsing YAML logic
    rets = []
    for k, v in pipeline.get("children", {}).items():
        ret = fn(k, v, *args, **kwargs)
        if ret is not None:
            rets.append(ret)
    return rets if rets else None


def find_pipeline(pipeline: PipelineDict, select_fn: Callable[[str, PipelineDict], bool]) -> PipelineDict:
    def _find(name_, pipeline_):
        if select_fn(name_, pipeline_):
            return pipeline_
        rv = recurse_pipeline(pipeline_, _find)
        return rv[0] if rv is not None else None

    if select_fn("", pipeline):
        return pipeline
    return _find("", pipeline)


def find_pipeline_path(pipeline: PipelineDict, select_fn: Callable[[str, PipelineDict], bool]) -> list[str] | None:
    """
    Find a path of children from the root to the target selected by `select_fn`
    """

    def _find(name_: str, pipeline_: PipelineDict) -> list[str] | None:
        if select_fn(name_, pipeline_):
            return [name_]
        rv = recurse_pipeline(pipeline_, _find)
        assert rv is None or len(rv) == 1
        return list(itertools.chain([name_], rv[0])) if rv is not None else None

    if select_fn("", pipeline):
        return []
    path = _find("", pipeline)
    return path[1:] if path else None


def find_all_pipeline(pipeline: PipelineDict, select_fn: Callable[[str, PipelineDict], bool]) -> list[PipelineDict]:
    """Find all sub-pipelines for which select_fn is True"""

    def _find(name_, pipeline_):
        rv = []
        if select_fn(name_, pipeline_):
            rv.append(pipeline_)
        rv2 = recurse_pipeline(pipeline_, _find)
        return rv + list(itertools.chain.from_iterable(rv2) if rv2 is not None else [])

    # if select_fn("", pipeline):
    #     return pipeline
    return _find("", pipeline) or []


def collect_jobs_pipeline(yaml_data: dict) -> PipelineDict:
    def fill_pipeline(name: str, pipeline: Union[dict, list], variables: dict) -> dict[str, PipelineDict] | None:
        variables_ = variables.copy()
        if name in special_keys:
            return None
        server_ = None
        if recurse_ := (
            pipeline.get("$recurse", variables_.get("recurse"))
            if isinstance(pipeline, dict)
            else variables_.get("recurse")
        ):
            variables_["recurse"] = recurse_
        if name and not name.startswith("."):
            server_ = variables_.get("server")
        else:
            name = name[1:]
        p = PipelineDict(
            name=name,
            children={},
            uuid=str(uuid.uuid4()),
            recurse=recurse_ or False,
        )
        if isinstance(pipeline, dict):
            if label := pipeline.get("$label"):
                p["label"] = label
        if server_:
            p["server"] = server_
        children = recurse_yaml(pipeline, fill_pipeline, variables_)
        mergedeep.merge(p["children"], *children, strategy=mergedeep.Strategy.TYPESAFE_ADDITIVE) if children else None
        return {name: p}

    # struct: collections.OrderedDict = collections.OrderedDict()
    pipelines: dict[str, PipelineDict] = {}
    for server, data in yaml_data["servers"].items():
        tmp: dict[str, PipelineDict]
        for k in data["pipelines"]:
            if type(data["pipelines"]) is dict:
                tmp = fill_pipeline(k, data["pipelines"][k], {"server": server}) or dict()
            else:
                tmp = fill_pipeline(k, [], server) or dict()
            mergedeep.merge(pipelines, tmp, strategy=mergedeep.Strategy.TYPESAFE_ADDITIVE)
    return PipelineDict(
        name="",
        children=pipelines,
        uuid=str(uuid.uuid4()),
    )


def add_recursive_jobs_pipeline(pipeline: PipelineDict, job_data: JobDataDict) -> PipelineDict:
    def fill_pipeline(name: str, pipeline_: PipelineDict):
        if "server" in pipeline_ and pipeline_.get("recurse") and job_data.get(name, JobData.UNDEFINED).downstream:
            server = pipeline_["server"]
            for k, v in job_data[name].downstream.items():
                pipeline_["children"].setdefault(
                    k,
                    PipelineDict(
                        name=k,
                        children={},
                        uuid=str(uuid.uuid4()),
                        recurse=True,
                    ),
                ).setdefault("server", v)
        recurse_pipeline(pipeline_, fill_pipeline)

    fill_pipeline("", pipeline)
    return pipeline


def collect_jobs_dict(yaml_data: dict) -> dict[JobName, str]:
    def fill_pipeline(name: str, pipeline: Union[dict, list], server: str, out_struct: dict):
        if name in special_keys:
            return None
        recurse_yaml(pipeline, fill_pipeline, server, out_struct)
        if not name.startswith("."):
            out_struct[name] = server

    struct: collections.OrderedDict = collections.OrderedDict()
    for server, data in yaml_data["servers"].items():
        for k in data["pipelines"]:
            if type(data["pipelines"]) is dict:
                fill_pipeline(k, data["pipelines"][k], server, struct)
            else:
                fill_pipeline(k, [], server, struct)
    return struct


def get_downstream_serials(d: PipelineDict, job_data: dict) -> set[str]:
    def _collect(name, sub_dict: PipelineDict) -> set[str] | None:
        serials_: set[str] = set()
        serial = job_data.get(name, JobData.UNDEFINED).serial
        if serial:
            return {serial}
        other_serials = recurse_pipeline(sub_dict, _collect)
        if other_serials:
            serials_ |= set(itertools.chain.from_iterable(other_serials))
        return serials_ if serials_ else None

    serials = _collect(d["name"], d)
    return serials if serials else set()


@timeit
def translate_uuid(
    uuid: str, old_pipeline: PipelineDict, new_pipeline: PipelineDict
) -> tuple[str, PipelineDict] | None:
    sub_dict: PipelineDict = new_pipeline
    path = find_pipeline_path(old_pipeline, lambda _, p: p.get("uuid", "") == uuid)
    if path is not None:
        # pprint(path)
        for child in path:
            sub_dict = sub_dict.get("children", {}).get(child, {})  # type: ignore
        if sub_dict:
            return sub_dict["uuid"], sub_dict
    return None
