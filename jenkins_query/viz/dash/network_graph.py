import time
from typing import List, Tuple, TypedDict

import networkx  # type: ignore
import networkx as nx

from jenkins_query.pipeline_utils import PipelineDict


class NodeCustomData(TypedDict):
    downstream_status: str
    layer: int
    name: str
    serial: str
    status: str
    url: str


def generate_nx(job_tree: PipelineDict, job_data: dict) -> networkx.DiGraph:
    def get_nodes(d: PipelineDict, parent="", depth=0) -> Tuple[dict, List[Tuple[str, str]]]:
        _nodes = dict()
        _edges = []
        if parent == "" and d["name"]:
            id = d["name"]
            if id in job_data:
                status = d["status"]
            else:
                status = d["downstream_status"]
            if status is None:
                status = "In Progress"
            custom_data: NodeCustomData = {
                "layer": depth,
                "status": status,
                "downstream_status": d["downstream_status"],
                "url": job_data[id]["url"] if id in job_data else None,
                "serial": job_data[id]["serial"]
                if id in job_data and "serial" in job_data[id] and job_data[id]["serial"]
                else 0,
                "name": id,
            }
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
            custom_data: NodeCustomData = {
                "layer": depth,
                "status": status,
                "downstream_status": data["downstream_status"],
                "url": job_data[name]["url"] if name in job_data else None,
                "serial": job_data[name]["serial"]
                if name in job_data and "serial" in job_data[name] and job_data[name]["serial"]
                else 0,
                "name": name,
            }
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
