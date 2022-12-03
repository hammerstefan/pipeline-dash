from __future__ import annotations

import collections
import itertools
import uuid
from typing import Any, Callable, Concatenate, ParamSpec, TypedDict, Union

import mergedeep  # type: ignore
from typing_extensions import NotRequired


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
    "label",
    "recurse",
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


def collect_jobs_pipeline(yaml_data: dict) -> PipelineDict:
    def fill_pipeline(name: str, pipeline: Union[dict, list], server: str) -> dict[str, PipelineDict] | None:
        server_ = None
        recurse_ = False
        if name in special_keys:
            return None
        if name and not name.startswith("."):
            server_ = server
            recurse_ = pipeline["recurse"] if isinstance(pipeline, dict) and "recurse" in pipeline else False
        else:
            name = name[1:]
        p = PipelineDict(
            name=name,
            children={},
            uuid=str(uuid.uuid4()),
            recurse=recurse_,
        )
        if isinstance(pipeline, dict):
            if label := pipeline.get("label"):
                p["label"] = label
        if server_:
            p["server"] = server_
        children = recurse_yaml(pipeline, fill_pipeline, server)
        mergedeep.merge(p["children"], *children, strategy=mergedeep.Strategy.TYPESAFE_ADDITIVE) if children else None
        return {name: p}

    # struct: collections.OrderedDict = collections.OrderedDict()
    pipelines: dict[str, PipelineDict] = {}
    for server, data in yaml_data["servers"].items():
        tmp: dict[str, PipelineDict]
        for k in data["pipelines"]:
            if type(data["pipelines"]) is dict:
                tmp = fill_pipeline(k, data["pipelines"][k], server) or dict()
            else:
                tmp = fill_pipeline(k, [], server) or dict()
            mergedeep.merge(pipelines, tmp, strategy=mergedeep.Strategy.TYPESAFE_ADDITIVE)
    return PipelineDict(
        name="",
        children=pipelines,
        uuid=str(uuid.uuid4()),
    )


def add_recursive_jobs_pipeline(pipeline: PipelineDict, job_data: dict) -> PipelineDict:
    def fill_pipeline(name: str, pipeline_: PipelineDict):
        if "server" in pipeline_ and name in job_data and "downstream" in job_data[name]:
            server = pipeline_["server"]
            for k, v in job_data[name]["downstream"].items():
                pipeline_["children"].setdefault(
                    k,
                    PipelineDict(
                        name=k,
                        children={},
                        uuid=str(uuid.uuid4()),
                    ),
                ).setdefault("server", v)
        recurse_pipeline(pipeline_, fill_pipeline)

    fill_pipeline("", pipeline)
    return pipeline


def collect_jobs_dict(yaml_data: dict) -> dict:
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
        serial = job_data.get(name, {}).get("serial")
        if serial:
            return {serial}
        other_serials = recurse_pipeline(sub_dict, _collect)
        if other_serials:
            serials_ |= set(itertools.chain.from_iterable(other_serials))
        return serials_ if serials_ else None

    serials = _collect(d["name"], d)
    return serials if serials else set()
