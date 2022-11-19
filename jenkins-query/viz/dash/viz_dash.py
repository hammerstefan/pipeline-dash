import itertools
import time
import uuid
from functools import wraps
from pprint import pprint
from statistics import median
from typing import List, Tuple, Dict

import dash
import networkx
import plotly.graph_objects as go
import networkx as nx
from dash import html, dcc, Input, Output, MATCH, State
import dash_bootstrap_components as dbc
import dash_bootstrap_templates
from dash.exceptions import PreventUpdate
from dash_extensions import enrich as de

from pipeline_utils import find_pipeline
from viz.dash import components


def timeit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.process_time()
        ret = f(*args, **kwargs)
        end_time = time.process_time()
        print(f"{getattr(f, '__name__', None)} executed in {end_time - start_time} sec")
        return ret
    return wrapper


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
                    status = data['__downstream_status__']
                if status is None:
                    status = "In Progress"
                _nodes[id] = {
                    "layer": depth,
                    "status": status,
                    "downstream_status": data['__downstream_status__'],
                    "url": job_data[name]["url"] if name in job_data else None,
                    "serial": job_data[name]["serial"] if name in job_data and "serial" in job_data[name] and
                                                          job_data[name]["serial"] else 0,
                    "name": name,
                }
                if parent:
                    _edges += [(parent, id)]
                new_nodes, new_edges = get_nodes(data, id, depth + 1)
                _nodes.update(new_nodes)
                _edges += new_edges
        return _nodes, _edges

    nodes, edges = get_nodes(job_tree)
    graph = nx.DiGraph()
    graph.add_edges_from(edges)
    for n, v in nodes.items():
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
            next_y = recurse(s, g, depth + 1, next_y)
        next_ys = [g.nodes[s]["pos"][1] for s in g.successors(n)]
        median_y = median(next_ys) if next_ys else y
        g.nodes[n]["pos"] = (float(depth), median_y)
        return next_y

    first_nodes = [n for n in g.nodes() if g.nodes[n]["layer"] == 0]
    ny = 0
    for n in first_nodes:
        ny = recurse(n, g, 0, ny)
        ny += 2

    return ny


def size_traces(scale: float,
                node_trace: go.Scatter,
                edge_traces: Dict[str, go.Scatter],
                annotations: List[go.layout.Annotation]):
    node_trace.marker.size *= scale
    for et in edge_traces.values():
        et.line.width *= scale
    for an in annotations:
        an.xshift *= scale if scale < 0 else pow(scale, 1.2)
        an.yshift = 5
        # an.yshift *= max(scale, 2.0)
        an.font.size = min(max(int(an.font.size * scale), 6), 24)


def generate_plot_figure(graph: networkx.Graph) -> go.Figure:
    start_time = time.process_time()
    # pos = nx.multipartite_layout(graph, subset_key="layer", center=(0,1))
    serial = str(max(float(graph.nodes[n]["data"]["serial"]) for n in graph.nodes()))
    y_scale = do_layout(graph)

    edge_traces = generate_edge_traces(graph)

    node_text_dict, node_trace = generate_node_traces(graph)

    annotations = get_node_labels(graph, node_text_dict)
    size_traces(50/y_scale, node_trace, edge_traces, annotations)
    y_scale_limit = 100
    layoutButtons = list([
        dict(type="buttons",
             active=0 if y_scale < y_scale_limit else 1,
             buttons=list([
                 dict(label='Label:On',
                      method='update',
                      args=[{'visible': True}, {'annotations': annotations}]
                      ),
                 dict(label='Label:Off',
                      method='update',
                      args=[{'visible': True}, {'annotations': []}]
                      ),
             ]
             )
             )
    ]
    )
    fig = go.Figure(data=[*edge_traces.values(), node_trace],
                    layout=go.Layout(
                        titlefont_size=16,
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=10, l=5, r=5, t=0, pad=0),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(
                            showgrid=False,
                            zeroline=False,
                            showticklabels=False,
                            range=[-4, y_scale],
                            constraintoward="top",
                        ),
                        height=y_scale * 15,
                        # paper_bgcolor="white",
                        # plot_bgcolor="white",
                        # title=f"Pipeline for {serial}",
                        # autosize=True,
                        annotations=annotations if y_scale < y_scale_limit else [],
                        updatemenus=layoutButtons,
                        uirevision=str(uuid.uuid4()),
                    ),
                    )
    fig.update
    # fig.update_layout(annotations=annotations)

    end_time = time.process_time()
    print(f"Rendered graph in {end_time - start_time} sec")
    return fig


def get_node_labels(graph, node_text_dict):
    annotations = [go.layout.Annotation(
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
    ) for n in graph.nodes()]
    return annotations


def generate_node_traces(graph):
    node_trace = go.Scatter(
        x=[pos[0] for _, pos in graph.nodes.data("pos")],
        y=[pos[1] for _, pos in graph.nodes.data("pos")],
        mode='markers',
        textposition="middle right",
        hovertemplate='%{customdata.name}<br>%{customdata.serial}<extra></extra>',
        showlegend=False,
        marker=dict(
            size=15,
            line_width=0,
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
        edge[1]: find_unique_in_name(
            graph.nodes[edge[0]]["data"]["name"],
            graph.nodes[edge[1]]["data"]["name"]) for edge in graph.edges()
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
    return node_text_dict, node_trace


def generate_edge_traces(graph):
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
                                                  (graph.nodes[edge[0]]["pos"][0] + graph.nodes[edge[1]]["pos"][0]) / 2,
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
    return edge_traces


def display_dash(pipeline_dict: dict, job_data: dict):
    start_time = time.process_time()
    graph = generate_nx(pipeline_dict, job_data)
    end_time = time.process_time()
    print(f"Generated network in {end_time - start_time} sec")
    app = de.DashProxy(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP,
                              dbc.icons.BOOTSTRAP,
                              ],
        transforms=[
            de.TriggerTransform(),
            # de.MultiplexerTransform(),
            de.NoOutputTransform(),
            # de.OperatorTransform(),
        ],
    )
    dash_bootstrap_templates.load_figure_template()
    fig = generate_plot_figure(graph)
    graph = dcc.Graph(
        id='pipeline-graph',
        figure=fig,
        style={
            # "min-height": fig.layout.height/4,
            "height": "90vh",
            "display": "block",
        },
        responsive=True,
    )

    layout_left_pane, btn_list = components.left_pane(pipeline_dict, job_data)
    layout_graph = dbc.Col(
        [dbc.Card([graph], body=True)],
        xxl=9, xl=8, lg=7, xs=12
    )

    def layout_container() -> dbc.Container:
        return dbc.Container(
            [
                dbc.Row(
                    [
                        layout_left_pane,
                        layout_graph,
                    ],
                    class_name="g-2"
                ),
                html.Div(id="hidden-div", hidden=True),
                html.Div(
                    children=[
                        html.Div(
                            id="input-btn-diagram"
                        )
                    ]
                ),
            ],
            fluid=True,
            id="dbc",
            className="dbc",
        )
    app.layout = layout_container()

    app.clientside_callback(
        """
        function(clickData) {
            url = clickData?.points[0]?.customdata?.url;
            if(url)
                window.open(url, "_blank");
            return null;
        }
        """,
        Output('hidden-div', 'children'),
        Input('pipeline-graph', 'clickData'),
        prevent_initial_call = True,
    )

    # @app.callback(
    #     Output("pipeline-graph", "figure"),
    #     inputs=[
    #         de.Trigger(b, "n_clicks") for b in btn_list
    #     ],
    #     prevent_initial_call=True,
    # )
    # def click_diagram_btn():
    #     nonlocal fig
    #     start_time = time.process_time()
    #     start_id = dash.ctx.triggered_id[12:]
    #     sub_dict = find_pipeline(pipeline_dict, lambda _, p: p.get("__uuid__", "") == start_id)
    #     graph = generate_nx(sub_dict, job_data)
    #     end_time = time.process_time()
    #     print(f"Generated network in {end_time - start_time} sec")
    #     fig = generate_plot_figure(graph)
    #     return fig

    # app.clientside_callback(
    #     """
    #     function(nclicks, id, open, children) {
    #         open = ! open;
    #         s = JSON.stringify(id, Object.keys(id).sort());
    #         dom = document.getElementById(s);
    #         elements = dom.getElementsByTagName("details");
    #         for (let e of elements)
    #             e.open = open;
    #         return open;
    #     }
    #     """,
    #     Output({"type": "details-job", "index": MATCH}, "open"),
    #     Input({"type": "btn-expand", "index": MATCH}, "n_clicks"),
    #     State({"type": "details-job", "index": MATCH}, "id"),
    #     State({"type": "details-job", "index": MATCH}, "open"),
    #     State({"type": "details-job", "index": MATCH}, "children"),
    #     prevent_initial_call=True,
    # )

    @app.callback(
        Input("pipeline-graph", "relayoutData"),
        prevent_initial_call=True,
    )
    def graph_relayout(data):
        # TODO scale graph nodes/traces/annotations to zoom level
        pprint(data)

    def setup_click_btn_left_pane_expand():
        this_toggle = False

        @app.callback(
            Output("col-left-pane", "style"),
            de.Trigger("btn-left-pane-expand", "n_clicks"),
            prevent_initial_call=True,
        )
        def click_btn_left_pane_expand():
            nonlocal this_toggle
            this_toggle = not this_toggle
            width = "100vw" if this_toggle else None
            return dict(width=width)
    setup_click_btn_left_pane_expand()

    @app.callback(
        Output("pipeline-graph", "figure"),
        Input("el-diagram-click", "event"),
        prevent_initial_call=True,
    )
    def input_btn_diagram(e: dict):
        uuid = e.get("detail")
        if uuid is None:
            raise PreventUpdate
        nonlocal fig
        start_time = time.process_time()
        sub_dict = find_pipeline(pipeline_dict, lambda _, p: p.get("__uuid__", "") == uuid)
        graph = generate_nx(sub_dict, job_data)
        end_time = time.process_time()
        print(f"Generated network in {end_time - start_time} sec")
        fig = generate_plot_figure(graph)
        return fig


    app.run_server(debug=True)


