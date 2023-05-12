from typing import Tuple

import dash  # type: ignore
import dash_bootstrap_components as dbc  # type: ignore
import dash_extensions.javascript as de_js  # type: ignore
import networkx  # type: ignore
from dash import dcc, html, Input, State  # type: ignore
from dash.development.base_component import Component  # type: ignore
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Operator, OperatorOutput
from plotly import graph_objects as go  # type: ignore

from pipeline_dash.viz.dash import components, viz_dash
from pipeline_dash.viz.dash.cache import cache
from pipeline_dash.viz.dash.components.jobs_pipeline_fig import generate_annotations_layout_update, generate_plot_figure
from pipeline_dash.viz.dash.logged_callback import logged_callback


class Ids:
    class StoreIds:
        show_annotations = "store-show-annotations"
        annotations_key = "store-annotations"

    graph = "pipeline-graph"
    stores = StoreIds


ids = Ids


def generate(app: dash.Dash, graph: networkx.DiGraph, session_id: str) -> Tuple[dbc.Col, go.Figure]:
    fig, show_annotations = generate_plot_figure(graph, session_id)
    graph = dcc.Graph(
        id=ids.graph,
        figure=fig,
        config=dict(
            modeBarButtonsToRemove=[
                "select2d",
                "lasso2d",
            ],
        ),
        style={
            # "min-height": fig.layout.height/4,
            "height": "97vh",
            # "height": "fit-content(75vh)",
            "display": "block",
            # "margin": "20px",
            "z-index": "-1",
        },
        responsive=True,
    )
    layout_graph = dbc.Col(
        [
            dbc.Card(
                [
                    html.Div(
                        [
                            components.GraphTooltip(app),
                            graph,
                            dcc.Store(id=Ids.stores.show_annotations, data=show_annotations),
                            dcc.Store(id=Ids.stores.annotations_key),
                        ],
                        style={"position": "relative"},
                    )
                ],
                body=True,
            )
        ],
        xxl=9,
        xl=8,
        lg=7,
        xs=12,
    )

    @app.callback(
        OperatorOutput(Ids.graph, "figure"),
        Input(Ids.stores.show_annotations, "data"),
        State(viz_dash.Ids.stores.session_id, "data"),
        State(viz_dash.Ids.stores.figure_root, "data"),
        prevent_initial_call=False,
    )
    @logged_callback
    # @pcprofile
    def cb_show_annotations(show_annotations_, session_id_, figure_root_):
        cached_val = cache.get(f"{session_id_}.show_annotations")
        import logging

        logging.info(f"CACHE {session_id_}.show_annotations: {cached_val}")
        # skip annotations update if we're already showing annotations and figure root has not changed
        if cached_val == show_annotations_ and figure_root_ is None:
            raise PreventUpdate()
        cache.set(f"{session_id_}.show_annotations", show_annotations_)
        graph_ = cache.get(f"{session_id_}.graph")
        layout_update, annotations = generate_annotations_layout_update(graph_, session_id_, show_annotations_)
        return Operator()["layout"].dict.update(layout_update)

    return layout_graph, fig
