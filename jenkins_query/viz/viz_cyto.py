# type: ignore
# file currently unused
from typing import List

import dash_cytoscape as dcyto
from dash import Dash, html


def generate_cyto_elements(job_tree: dict, job_data: dict) -> List[dict]:
    # todo fix this to work with PipelineDict
    def get_nodes(d: dict, parent="") -> List[dict]:
        _nodes = []
        _edges = []
        for name, data in d.items():
            if not name.startswith("__") and not name.endswith("__"):
                id = f"{parent}&{name}"
                _nodes += [
                    {
                        "data": {"id": id, "name": name},
                    }
                ]
                if "__server__" not in data:
                    _nodes[-1]["classes"] = "group"
                else:
                    _nodes[-1]["classes"] = "job"
                status_map = {
                    "FAILURE": "red",
                    "SUCCESS": "green",
                    "UNSTABLE": "orange",
                    "In Progress": "yellow",
                    None: "yellow",
                    "default": "gray",
                }
                if name in job_data:
                    _nodes[-1]["classes"] += f" {status_map.get(job_data[name]['status'], status_map['default'])}"
                else:
                    _nodes[-1]["classes"] += f" {status_map.get(data['__status__'], status_map['default'])}"
                if parent:
                    _edges += [
                        {
                            "data": {"source": parent, "target": id},
                            "classes": f"{status_map.get(data['__status__'], status_map['default'])}",
                        }
                    ]
                new_nodes, new_edges = get_nodes(data, id)
                _nodes += new_nodes
                _edges += new_edges
        return _nodes, _edges

    nodes, edges = get_nodes(job_tree)
    return nodes + edges


def display_cyto(elements):
    dcyto.load_extra_layouts()
    app = Dash(__name__)

    app.layout = html.Div(
        [
            dcyto.Cytoscape(
                id="cytoscape-elements-basic",
                # layout={
                #     "name": "breadthfirst",
                #     "directed": True,
                # },
                layout={
                    "name": "dagre",
                    # "rankDir": "LR",
                    # "ranker": "longest-path",
                    "nodeSep": "0",
                    "rankSep": "0",
                    "nodeDimensionsIncludeLabels": True,
                },
                style={"width": "100%", "min-height": "1000px", "height": "auto"},
                stylesheet=[
                    {
                        "selector": "edge",
                        "style": {"width": 10, "line-color": "#ccc", "curve-style": "bezier"},
                    },
                    {
                        "selector": ".group",
                        "style": {"content": "data(name)"},
                    },
                    {
                        "selector": ".job",
                        "style": {
                            "content": "data(name)",
                            "text-rotation": "45",
                            "text-halign": "right",
                            "text-valign": "center",
                            "text-margin-x": "-10",
                            "text-margin-y": "15",
                        },
                    },
                    {
                        "selector": ".red",
                        "style": {"background-color": "darkred", "line-color": "darkred"},
                    },
                    {
                        "selector": ".green",
                        "style": {
                            "background-color": "green",
                            "line-color": "green",
                        },
                    },
                    {
                        "selector": ".orange",
                        "style": {
                            "background-color": "orange",
                            "line-color": "orange",
                        },
                    },
                    {
                        "selector": ".yellow",
                        "style": {
                            "background-color": "gold",
                            "line-color": "gold",
                        },
                    },
                    {
                        "selector": ".gray",
                        "style": {
                            "background-color": "gray",
                            "line-color": "gray",
                        },
                    },
                ],
                elements=elements,
            ),
            html.Pre(
                id="cytoscape-tapNodeData-json",
                style={
                    "border": "thin lightgrey solid",
                    "overflowX": "scroll",
                },
            ),
        ]
    )

    app.run_server(debug=True)
