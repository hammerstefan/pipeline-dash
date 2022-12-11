from __future__ import annotations

import time
from typing import List, Optional, Tuple, TypedDict

import networkx  # type: ignore
import networkx as nx
from typing_extensions import NotRequired

from pipeline_dash.job_data import JobData, JobDataDict
from pipeline_dash.pipeline_utils import get_downstream_serials, PipelineDict


class NodeCustomData(TypedDict):
    downstream_status: str
    layer: int
    name: str
    serial: Optional[str | list[str]]
    status: str
    url: str | None
    label: NotRequired[str]
    uuid: str
    # downstream_serials: tuple[str, ...]


def generate_nx(job_tree: PipelineDict, job_data: JobDataDict) -> networkx.DiGraph:
    def generate_custom_data(
        d: PipelineDict,
        job_data: JobDataDict,
        depth: int,
    ) -> NodeCustomData:
        name = d["name"]
        if name in job_data:
            status = d["status"]
        else:
            status = d["downstream_status"]
        if status is None:
            status = "In Progress"
        custom_data: NodeCustomData = {
            "layer": depth,
            "status": status,
            "downstream_status": d["downstream_status"],
            "url": job_data[name].url if name in job_data else None,
            "serial": job_data.get(name, JobData.UNDEFINED).serial or sorted(get_downstream_serials(d, job_data)),
            "name": name,
            "uuid": d["uuid"],
            # "downstream_serials": tuple(get_downstream_serials(d)),
        }
        if label := d.get("label"):
            custom_data["label"] = label

        return custom_data

    def get_nodes(d: PipelineDict, parent="", depth=0) -> Tuple[dict, List[Tuple[str, str]]]:
        _nodes = dict()
        _edges = []
        if parent == "" and not d["name"]:
            for name, data in d["children"].items():
                new_nodes, new_edges = get_nodes(data, "", 0)
                _nodes.update(new_nodes)
                _edges += new_edges
        else:
            if parent == "" and d["name"]:
                id = d["name"]
                custom_data = generate_custom_data(d, job_data, depth)
                _nodes[id] = custom_data
                parent = id
                depth = 1
            for name, data in d["children"].items():
                id = f"{parent}.{name}"
                if name in job_data:
                    status = data["status"]
                else:
                    status = data["downstream_status"]
                if status is None:
                    status = "In Progress"
                custom_data = generate_custom_data(data, job_data, depth)
                _nodes[id] = custom_data
                if parent:
                    _edges += [(parent, id)]
                new_nodes, new_edges = get_nodes(data, id, depth + 1)
                _nodes.update(new_nodes)
                _edges += new_edges
        return _nodes, _edges

    start_time = time.process_time()
    nodes, edges = get_nodes(job_tree)
    graph = nx.DiGraph()
    graph.add_edges_from(edges)
    for n, v in nodes.items():
        layer = v["layer"]
        # del v["layer"]
        graph.add_node(n, layer=layer, data=v)
    end_time = time.process_time()
    print(f"Generated network in {end_time - start_time} sec")
    return graph
