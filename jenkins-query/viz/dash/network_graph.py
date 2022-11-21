import time
from typing import List, Tuple

import networkx
import networkx as nx


def generate_nx(job_tree: dict, job_data: dict) -> networkx.DiGraph:
    def get_nodes(d: dict, parent="", depth=0) -> Tuple[dict, List[Tuple[str, str]]]:
        _nodes = dict()
        _edges = []
        for name, data in d.items():
            if not name.startswith("__") and not name.endswith("__"):
                id = f"{parent}.{name}"
                if name in job_data:
                    status = data["__status__"]
                else:
                    status = data["__downstream_status__"]
                if status is None:
                    status = "In Progress"
                _nodes[id] = {
                    "layer": depth,
                    "status": status,
                    "downstream_status": data["__downstream_status__"],
                    "url": job_data[name]["url"] if name in job_data else None,
                    "serial": job_data[name]["serial"]
                    if name in job_data and "serial" in job_data[name] and job_data[name]["serial"]
                    else 0,
                    "name": name,
                }
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
        del v["layer"]
        graph.add_node(n, layer=layer, data=v)
    end_time = time.process_time()
    print(f"Generated network in {end_time - start_time} sec")
    return graph
