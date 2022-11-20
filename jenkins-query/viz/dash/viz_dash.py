import time
from functools import wraps
from pprint import pprint
from typing import List, Tuple

import networkx
import networkx as nx
from dash import html, Input, Output, State
import dash_bootstrap_components as dbc
import dash_bootstrap_templates
from dash.exceptions import PreventUpdate
from dash_extensions import enrich as de

import viz.dash.components.jobs_pipeline_fig
from pipeline_utils import find_pipeline
from viz.dash import components
from viz.dash.components.graph_col import generate
from viz.dash.components.jobs_pipeline_fig import generate_plot_figure


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
            de.MultiplexerTransform(),
            de.NoOutputTransform(),
            # de.OperatorTransform(),
        ],
    )
    dash_bootstrap_templates.load_figure_template()

    layout_left_pane, btn_list = components.left_pane.generate(pipeline_dict, job_data)
    layout_graph, fig = components.graph_col.generate(graph)

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
        Output("pipeline-graph", "figure"),
        Input("pipeline-graph", "relayoutData"),
        State("pipeline-graph", "figure"),
        prevent_initial_call=True,
    )
    def graph_relayout(data, figure):
        # TODO scale graph nodes/traces/annotations to zoom level
        if not data:
            raise PreventUpdate
        delta = data.get('yaxis.range[1]', 0) - data.get('yaxis.range[0]', 0)
        if not delta:
            if 'autosize' in data or 'yaxis.autorange' in data:
                delta = None
                # fig.layout.autosize = True
            else:
                raise PreventUpdate
        # else:
        #     fig.layout.autosize = False
        #     fig.layout.yaxis.range = [data['yaxis.range[0]'], data['yaxis.range[1]']]
        #     if 'xaxis.range[0]' in data and 'xaxis.range[1]' in data:
        #         fig.layout.xaxis.range = [data['xaxis.range[0]'], data['xaxis.range[1]']]
        #     else:
        #         fig.layout.xaxis.autorange = True

        components.jobs_pipeline_fig.resize_fig_data_from_y_delta(figure, delta)
        return figure

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
        fig = viz.dash.components.jobs_pipeline_fig.generate_plot_figure(graph)
        return fig

    @app.callback(
        [
            Output("pipeline-graph", "figure"),
            Output("pipeline-graph", "responsive"),
        ],
        Input("cb-responsive-graph", "value"),
        State("pipeline-graph", "figure"),
        prevent_initial_call=True,
    )
    def btn_responsive_graph(responsive, figure):
        if not responsive:
            components.jobs_pipeline_fig.resize_fig_data_from_scale(figure, 0.8)
        else:
            components.jobs_pipeline_fig.resize_fig_data_from_y_delta(figure, None)
        return figure, responsive


    app.run_server(debug=True)


