import itertools
import time
import uuid
from statistics import median
from typing import Dict, List, Optional

import networkx  # type: ignore
from plotly import graph_objects as go  # type: ignore


def do_layout(g: networkx.DiGraph) -> int:
    def recurse(n, g, depth, y):
        first = True
        next_y = y
        for s in reversed(list(g.successors(n))):
            if first:
                first = False
            else:
                next_y += 1
            next_y = recurse(s, g, depth + 1, next_y)
        next_ys = [g.nodes[s]["pos"][1] for s in g.successors(n)]
        median_y = median(next_ys) if next_ys else y
        g.nodes[n]["pos"] = (float(depth), median_y)
        return next_y

    first_nodes = [n for n in g.nodes() if g.nodes[n]["layer"] == 0]
    ny = 0
    for n in reversed(first_nodes):
        ny = recurse(n, g, 0, ny)
        ny += 2

    return ny


def size_traces(
    scale: float, node_trace: go.Scatter, edge_traces: Dict[str, go.Scatter], annotations: List[go.layout.Annotation]
):
    node_trace.marker.size = max(node_trace.marker.size * scale, 2)
    for et in edge_traces.values():
        et.line.width = max(et.line.width * scale, 0.5)
    for an in annotations:
        an.xshift *= scale if scale < 0 else pow(scale, 1.2)
        an.yshift = 5
        # an.yshift *= max(scale, 2.0)
        an.font.size = min(max(int(an.font.size * scale), 6), 24)


def generate_plot_figure(graph: networkx.DiGraph) -> go.Figure:
    start_time = time.process_time()
    # pos = nx.multipartite_layout(graph, subset_key="layer", center=(0,1))
    # serial = str(max(float(graph.nodes[n]["data"]["serial"]) for n in graph.nodes()))
    y_scale = do_layout(graph)

    edge_traces = generate_edge_traces(graph)
    default_edge_width = next(iter(edge_traces.values())).line.width

    node_text_dict, node_trace = generate_node_traces(graph)
    default_node_size = node_trace.marker.size

    annotations = get_node_labels(graph, node_text_dict)
    default_scaling = 50 / y_scale
    size_traces(default_scaling, node_trace, edge_traces, annotations)
    y_scale_limit = 100
    layoutButtons = list(
        [
            dict(
                type="dropdown",
                active=0 if y_scale < y_scale_limit else 1,
                buttons=list(
                    [
                        dict(label="Label:On", method="update", args=[{"visible": True}, {"annotations": annotations}]),
                        dict(label="Label:Off", method="update", args=[{"visible": True}, {"annotations": []}]),
                    ]
                ),
            )
        ]
    )
    fig = go.Figure(
        data=[*edge_traces.values(), node_trace],
        layout=go.Layout(
            # paper_bgcolor="white",
            # plot_bgcolor="white",
            # title=f"Pipeline for {serial}",
            annotations=annotations if y_scale < y_scale_limit else [],
            autosize=True,
            height=y_scale * 15,
            hovermode="closest",
            margin=dict(b=10, l=5, r=5, t=0, pad=0),
            meta=dict(
                default_edge_width=default_edge_width,
                default_node_size=default_node_size,
                default_scaling=default_scaling,
                default_yaxis_range=[-4, y_scale],
            ),
            selectdirection="v",
            showlegend=False,
            titlefont_size=16,  # type: ignore
            uirevision=str(uuid.uuid4()),
            updatemenus=layoutButtons,
            xaxis=dict(
                showgrid=False,
                showticklabels=False,
                zeroline=False,
            ),
            yaxis=dict(
                constraintoward="top",
                range=[-4, y_scale],
                showgrid=False,
                showticklabels=False,
                zeroline=False,
            ),
        ),
    )
    # fig.update_layout(annotations=annotations)

    end_time = time.process_time()
    print(f"Rendered graph in {end_time - start_time} sec")
    return fig


def get_node_labels(graph, node_text_dict):
    annotations = [
        go.layout.Annotation(
            x=graph.nodes[n]["pos"][0],
            y=graph.nodes[n]["pos"][1],
            xshift=5,
            yshift=5,
            xref="x",
            yref="y",
            text=node_text_dict.get(n, n),
            font=dict(
                size=12,
            ),
            align="left",
            showarrow=False,
            yanchor="top",
            xanchor="left",
            textangle=25,
            bgcolor="white",
            opacity=0.8,
        )
        for n in graph.nodes()
    ]
    return annotations


def generate_node_traces(graph):
    node_trace = go.Scatter(
        x=[pos[0] for _, pos in graph.nodes.data("pos")],
        y=[pos[1] for _, pos in graph.nodes.data("pos")],
        mode="markers",
        textposition="middle right",
        hovertemplate="%{customdata.name}<br>%{customdata.serial}<extra></extra>",
        showlegend=False,
        marker=dict(
            size=15,
            line_width=0,
        ),
    )

    def find_unique_in_name(a: str, b: str):
        al = a.split("-")
        bl = b.split("-")
        i = 0
        for i, t in enumerate(al):
            if t != bl[i]:
                break
        return "-".join(bl[i:])

    node_text_dict = {
        edge[1]: find_unique_in_name(graph.nodes[edge[0]]["data"]["name"], graph.nodes[edge[1]]["data"]["name"])
        for edge in graph.edges()
    }
    node_text = list(node_text_dict.get(n, n) for n in graph.nodes())
    node_trace.text = node_text
    node_trace.customdata = [graph.nodes[n]["data"] for n in graph.nodes()]
    node_color = []
    for n in graph.nodes():
        status = graph.nodes[n]["data"]["status"]
        status_map = {
            "FAILURE": "darkred",
            "SUCCESS": "#198754",
            "UNSTABLE": "orange",
            "In Progress": "#0dcaf0",
            None: "#0dcaf0",
            "default": "lightgray",
        }
        node_color.append(status_map.get(status, status_map["default"]))
    node_trace.marker.color = node_color
    return node_text_dict, node_trace


def generate_edge_traces(graph):
    edge_colors = []
    for edge in graph.edges():
        status_map = {
            "FAILURE": "#ff6666",
            "SUCCESS": "green",
            "UNSTABLE": "orange",
            "In Progress": "#3dd5f3",
            None: "#3dd5f3",
            "default": "gray",
        }
        status = graph.nodes[edge[1]]["data"]["downstream_status"]
        status_parent = graph.nodes[edge[0]]["data"]["downstream_status"]
        if status_parent == "NOT RUN":
            status = status_parent
        edge_colors.append(status_map.get(status, status_map["default"]))
    edge_traces = {
        color: go.Scatter(
            x=list(
                itertools.chain.from_iterable(
                    (
                        graph.nodes[edge[0]]["pos"][0],
                        (graph.nodes[edge[0]]["pos"][0] + graph.nodes[edge[1]]["pos"][0]) / 2,
                        graph.nodes[edge[1]]["pos"][0],
                        None,
                    )
                    for i, edge in enumerate(graph.edges())
                    if edge_colors[i] == color
                )
            ),
            y=list(
                itertools.chain.from_iterable(
                    (
                        graph.nodes[edge[0]]["pos"][1],
                        graph.nodes[edge[1]]["pos"][1],
                        graph.nodes[edge[1]]["pos"][1],
                        None,
                    )
                    for i, edge in enumerate(graph.edges())
                    if edge_colors[i] == color
                )
            ),
            line=dict(width=3, color=color),
            hoverinfo="none",
            mode="lines",
        )
        for color in set(edge_colors)
    }
    return edge_traces


def resize_fig_data_from_scale(fig: dict, scale: float):
    meta = fig["layout"]["meta"]
    default_node_size = meta["default_node_size"]
    default_edge_width = meta["default_edge_width"]
    for d in fig["data"]:  # type: dict
        if "marker" in d:
            d["marker"]["size"] = max(default_node_size * scale, 2)
        if "line" in d:
            d["line"]["width"] = max(default_edge_width * scale, 0.5)
    for an in itertools.chain(
        fig["layout"].get("annotations", []), fig["layout"]["updatemenus"][0]["buttons"][0]["args"][1]["annotations"]
    ):  # type: dict
        an["xshift"] = 5 * (scale if scale < 0 else pow(scale, 1.2))
        an["yshift"] = 5
        # an.yshift *= max(scale, 2.0)
        an["font"]["size"] = min(max(int(14 * scale), 6), 24)

    fig["layout"]["uirevision"] = str(uuid.uuid4())


def resize_fig_data_from_y_delta(fig: dict, new_y_delta: Optional[float]):
    meta = fig["layout"]["meta"]
    default_scaling = meta["default_scaling"]
    default_range = meta["default_yaxis_range"]
    scale = (
        ((default_range[1] - default_range[0]) / new_y_delta * default_scaling)
        if new_y_delta is not None
        else default_scaling
    )
    resize_fig_data_from_scale(fig, scale)
