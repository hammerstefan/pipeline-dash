import collections
import itertools
import time
import uuid
from statistics import median
from typing import Dict, Optional

import networkx  # type: ignore
from plotly import graph_objects as go  # type: ignore

from pipeline_dash.viz.dash.cache import cache


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


def scale_font_size(scale: float) -> float:
    # print(f"Font size scale: {scale}")
    return min(max(int(14 * scale), 6), 20)


def size_traces(scale: float, node_trace: go.Scatter, edge_traces: Dict[str, go.Scatter]):
    node_trace.marker.size = max(node_trace.marker.size * scale, 2)
    for et in edge_traces.values():
        et.line.width = max(et.line.width * scale, 0.5)


def size_annotations(scale: float, annotations: tuple[go.layout.Annotation, ...]):
    for an in annotations:
        an.xshift *= scale if scale < 0 else pow(scale, 1.2)
        an.yshift = 5
        # an.yshift *= max(scale, 2.0)
        an.font.size = scale_font_size(scale)


class NetworkPlotFigure:
    def __init__(self):
        pass


ShowAnnotations = bool


# @pcprofile
def generate_plot_figure(graph: networkx.DiGraph, session_id: str) -> tuple[go.Figure, ShowAnnotations]:
    start_time = time.process_time()
    # pos = nx.multipartite_layout(graph, subset_key="layer", center=(0,1))
    # serial = str(max(float(graph.nodes[n]["data"]["serial"]) for n in graph.nodes()))
    y_scale = do_layout(graph)

    edge_traces = generate_edge_traces(graph)
    default_edge_width = next(iter(edge_traces.values())).line.width

    node_trace = generate_node_traces(graph)
    default_node_size = node_trace.marker.size

    default_scaling = 50 / y_scale
    default_scaling = min(default_scaling, 3.0)
    cache.set(f"{session_id}.figure_default_scaling", default_scaling)
    size_traces(default_scaling, node_trace, edge_traces)
    y_scale_limit = 100
    fig = go.Figure(
        layout=go.Layout(
            autosize=True,
            hovermode="closest",
            margin=go.layout.Margin(b=0, t=0, l=0, r=0),
            selectdirection="v",
            showlegend=False,
            titlefont_size=16,  # type: ignore
            xaxis=dict(
                showgrid=False,
                showticklabels=False,
                zeroline=False,
            ),
            yaxis=dict(
                constraintoward="top",
                showgrid=False,
                showticklabels=False,
                zeroline=False,
            ),
        ),
    )
    fig.update(
        data=(*edge_traces.values(), node_trace),
        overwrite=True,
    )
    fig.update_layout(
        height=y_scale * 15,
        meta=dict(
            default_edge_width=default_edge_width,
            default_node_size=default_node_size,
            default_scaling=default_scaling,
            default_yaxis_range=[-4, y_scale],
        ),
        uirevision=str(uuid.uuid4()),
        overwrite=True,
    )
    fig.update_yaxes(range=[-4, y_scale], overwrite=True)
    show_annotations = bool(y_scale < y_scale_limit)
    cache.set(f"{session_id}.graph", graph)

    end_time = time.process_time()
    print(f"Rendered graph in {end_time - start_time} sec")
    return fig, show_annotations


LayoutUpdate = dict


# @pcprofile
def generate_annotations_layout_update(
    graph: networkx.DiGraph, session_id: str, show_annotations: bool
) -> tuple[LayoutUpdate, tuple[go.Annotation, ...]]:
    annotations = get_node_labels(graph) if show_annotations else tuple()
    cache.set(f"{session_id}.annotations", annotations)
    default_scaling = cache.get(f"{session_id}.figure_default_scaling")
    size_annotations(default_scaling, annotations)
    update_layout = dict(
        uirevision=str(uuid.uuid4()),
        annotations=annotations,
        overwrite=True,
    )
    return update_layout, tuple()


def get_node_labels(graph: networkx.DiGraph) -> tuple[go.Annotation, ...]:
    node_text_dict = _get_node_text_dict(graph)
    annotations = tuple(
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
            textangle=30,
            opacity=0.75,
        )
        for n in graph.nodes()
    )
    return annotations


def _find_unique_in_name(a: str, b: str):
    al = a.split("-")
    bl = b.split("-")
    alt, blt = (bl, al) if len(al) > len(bl) else (al, bl)
    i = 0
    for i, t in enumerate(alt):
        if t != blt[i]:
            break
    return "-".join(bl[i:])


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

    node_text_dict = _get_node_text_dict(graph)
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
    return node_trace


def _get_node_text_dict(graph: networkx.DiGraph):
    node_text_dict = {
        edge[1]: graph.nodes[edge[1]]["data"].get("label")
        or _find_unique_in_name(graph.nodes[edge[0]]["data"]["name"], graph.nodes[edge[1]]["data"]["name"])
        for edge in graph.edges()
    }
    return node_text_dict


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
        ds_status = graph.nodes[edge[1]]["data"]["downstream_status"]
        status = graph.nodes[edge[1]]["data"]["status"]
        counter = collections.Counter([ds_status, status])
        if counter["FAILURE"]:
            status = "FAILURE"
        elif counter["UNSTABLE"]:
            status = "UNSTABLE"
        elif counter["In Progress"] or status is None:
            status = "In Progress"
        elif counter["SUCCESS"]:
            status = "SUCCESS"
        else:
            status = "NOT RUN"
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
    print(f"Figure scale: {scale}")
    meta = fig["layout"]["meta"]
    default_node_size = meta["default_node_size"]
    default_edge_width = meta["default_edge_width"]
    for d in fig["data"]:  # type: dict
        if "marker" in d:
            d["marker"]["size"] = max(default_node_size * scale, 2)
        if "line" in d:
            d["line"]["width"] = max(default_edge_width * scale, 0.5)
    # todo renable with annotations from cache
    for an in itertools.chain(
        fig["layout"].get("annotations", []),
        # fig["layout"]["updatemenus"][0]["buttons"][0]["args"][0]["annotations"],
    ):  # type: dict
        an["xshift"] = 5 * (scale if scale < 0 else pow(scale, 1.2))
        an["yshift"] = 5
        # an.yshift *= max(scale, 2.0)
        an["font"]["size"] = scale_font_size(scale)

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
    scale = min(scale, 3.0)
    resize_fig_data_from_scale(fig, scale)
