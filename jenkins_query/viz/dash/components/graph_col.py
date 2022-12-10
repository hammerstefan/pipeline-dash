from typing import Tuple

import dash  # type: ignore
import dash_bootstrap_components as dbc  # type: ignore
import dash_extensions.javascript as de_js  # type: ignore
import networkx  # type: ignore
from dash import dcc, html, Input  # type: ignore
from dash.development.base_component import Component  # type: ignore
from plotly import graph_objects as go  # type: ignore

from jenkins_query.viz.dash import components
from jenkins_query.viz.dash.components.jobs_pipeline_fig import generate_plot_figure


class Ids:
    graph = "pipeline-graph"


ids = Ids


def generate(app: dash.Dash, graph: networkx.DiGraph) -> Tuple[dbc.Col, go.Figure]:
    fig = generate_plot_figure(graph)
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
    return layout_graph, fig
