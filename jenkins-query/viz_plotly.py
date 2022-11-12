import difflib
import itertools
import json
import os.path
import webbrowser
from statistics import median
from typing import List, Tuple, Set, Dict

import networkx
import plotly.graph_objects as go
import networkx as nx
from dash import Dash, html, dcc, Input, Output

def generate_nx(job_tree: dict, job_data: dict) -> networkx.DiGraph:
    def get_nodes(d: dict, parent="", depth=0) -> Tuple[dict, List[Tuple[str, str]]]:
        _nodes = dict()
        _edges = []
        for name, data in d.items():
            if not name.startswith("__") and not name.endswith("__"):
                id = name
                if name in job_data:
                    status = data["__status__"]
                else:
                    status = data['__downstream_status__']
                if status is None:
                    status = "In Progress"
                _nodes[id] = {
                    "layer": depth,
                    "status": status,
                    "downstream_status": data['__downstream_status__'],
                    "url": job_data[name]["url"] if name in job_data else None,
                    "serial": job_data[name]["serial"] if name in job_data and "serial" in job_data[name] and job_data[name]["serial"] else 0,
                    "name": name,
                }
                if parent:
                    _edges += [(parent, id)]
                new_nodes, new_edges = get_nodes(data, id, depth+1)
                _nodes.update(new_nodes)
                _edges += new_edges
        return _nodes, _edges


    nodes, edges = get_nodes(job_tree)
    graph = nx.DiGraph()
    graph.add_edges_from(edges)
    for n,v in nodes.items():
        layer = v["layer"]
        del v["layer"]
        graph.add_node(n, layer=layer, data=v)
    return graph


def do_layout(g: networkx.DiGraph) -> int:
    def recurse(n, g, depth, y):
        first = True
        next_y = y
        for s in g.successors(n):
            if first:
                first = False
            else:
                next_y += 1
            next_y = recurse(s, g, depth+1, next_y)
        next_ys = [g.nodes[s]["pos"][1] for s in g.successors(n)]
        median_y = median(next_ys) if next_ys else y
        g.nodes[n]["pos"] = (float(depth), median_y)
        return next_y

    first_nodes = [n for n in g.nodes() if g.nodes[n]["layer"] == 0]
    ny = 0
    for n in first_nodes:
        ny = recurse(n, g, 0, ny)

    return ny



def display_plotly(graph: networkx.Graph):
    # pos = nx.multipartite_layout(graph, subset_key="layer", center=(0,1))
    serial = str(max(float(graph.nodes[n]["data"]["serial"]) for n in graph.nodes()))
    y_scale = do_layout(graph)

    edge_colors = []
    for edge in graph.edges():
        status_map = {
            "FAILURE": "#ff6666",
            "SUCCESS": "green",
            "UNSTABLE": "orange",
            "In Progress": "#e6e600",
            None: "	#ff6666",
            "default": "gray",
        }
        status = graph.nodes[edge[1]]["data"]["downstream_status"]
        status_parent = graph.nodes[edge[0]]["data"]["downstream_status"]
        if status_parent == "NOT RUN":
            status = status_parent
        edge_colors.append(
            status_map.get(
                status,
                status_map["default"]
            ))

    edge_traces = {
        color: go.Scatter(
            x=list(
                itertools.chain.from_iterable((
                    graph.nodes[edge[0]]["pos"][0],
                    (graph.nodes[edge[0]]["pos"][0] + graph.nodes[edge[1]]["pos"][0])/2,
                    graph.nodes[edge[1]]["pos"][0],
                    None
                ) for i, edge in enumerate(graph.edges()) if edge_colors[i] == color)
            ),
            y=list(
                itertools.chain.from_iterable((
                    graph.nodes[edge[0]]["pos"][1],
                    graph.nodes[edge[1]]["pos"][1],
                    graph.nodes[edge[1]]["pos"][1],
                    None
                ) for i, edge in enumerate(graph.edges()) if edge_colors[i] == color)
            ),
            line=dict(width=3, color=color),
            hoverinfo='none',
            mode='lines',
        ) for color in set(edge_colors)
    }

    node_trace = go.Scatter(
        x=[pos[0] for _, pos in graph.nodes.data("pos")],
        y=[pos[1] for _, pos in graph.nodes.data("pos")],
        mode='markers',
        textposition="middle right",
        hovertemplate='%{customdata.name}<br>%{customdata.serial}<extra></extra>',
        showlegend=False,
        marker=dict(
            size=15,
            line_width=2,
        )
    )

    def find_unique_in_name(a: str, b: str):
        al = a.split("-")
        bl = b.split("-")
        for i, t in enumerate(al):
            if t != bl[i]:
                break
        return "-".join(bl[i:])

    node_text_dict = {
        edge[1]: find_unique_in_name(edge[0], edge[1]) for edge in graph.edges()
    }

    node_text = list(
        node_text_dict.get(n, n) for n in graph.nodes()
    )
    node_trace.text = node_text
    node_trace.customdata = [graph.nodes[n]["data"] for n in graph.nodes()]

    node_color = []
    for n in graph.nodes():
        status = graph.nodes[n]["data"]["status"]
        status_map = {
            "FAILURE": "darkred",
            "SUCCESS": "green",
            "UNSTABLE": "orange",
            "In Progress": "yellow",
            None: "yellow",
            "default": "lightgray",
        }
        node_color.append(status_map.get(status, status_map["default"]))
    node_trace.marker.color = node_color

    fig = go.Figure(data=[*edge_traces.values(), node_trace],
                    layout=go.Layout(
                        titlefont_size=16,
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20,l=5,r=5,t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=4000,
                        paper_bgcolor="white",
                        plot_bgcolor="white",
                        title=f"Pipeline for {serial}",
                    ),
                    )
    annotations = [go.layout.Annotation(
        x=graph.nodes[n]["pos"][0],
        y=graph.nodes[n]["pos"][1],
        xshift=5,
        yshift=5,
        xref="x",
        yref="y",
        text=node_text_dict.get(n, n),
        align="left",
        showarrow=False,
        yanchor="top",
        xanchor="left",
        textangle=25,
    ) for n in graph.nodes()]
    fig.update_layout(annotations=annotations)

    app = Dash(__name__)
    app.layout = html.Div(
        [
            dcc.Graph(
                id='pipeline-graph',
                figure=fig,
                style={"min-height": f"{y_scale*10}px", "height": "auto"},
            ),
            html.Div(id="hidden-div", hidden=True),
            html.Div(id="page-content"),
        ],
        id="global",
    )
    @app.callback(
        Output('page-content', 'children'),
        Input('pipeline-graph', 'clickData')
    )
    def display_click_data(clickData):
        try:
            print(clickData)
            url = clickData["points"][0]["customdata"]["url"]
            webbrowser.open(url)
            return html.A(url, href=url, target="_blank")
        except:
            return ""


    app.run_server(debug=True)
