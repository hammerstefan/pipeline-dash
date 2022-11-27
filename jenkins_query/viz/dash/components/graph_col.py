from typing import Tuple

import dash_bootstrap_components as dbc  # type: ignore
import dash_extensions.javascript as de_js  # type: ignore
import networkx  # type: ignore
from dash import dcc  # type: ignore
from plotly import graph_objects as go  # type: ignore

from jenkins_query.viz.dash.components.jobs_pipeline_fig import generate_plot_figure


def generate(graph: networkx.DiGraph) -> Tuple[dbc.Col, go.Figure]:
    fig = generate_plot_figure(graph)
    graph = dcc.Graph(
        id="pipeline-graph",
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
        },
        responsive=True,
    )
    layout_graph = dbc.Col([dbc.Card([graph], body=True)], xxl=9, xl=8, lg=7, xs=12)
    return layout_graph, fig
