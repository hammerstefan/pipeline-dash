# intended to be the bottom of screen job info pane
import dash_bootstrap_components as dbc
from dash import html

from jenkins_query.viz.dash import network_graph


class JobPane(dbc.Offcanvas):
    def __init__(self, data: network_graph.NodeCustomData, **kwargs):
        children_ = []
        if data:
            children_ = [
                dbc.Card(
                    dbc.Container(
                        [
                            dbc.Row(
                                dbc.Col(
                                    [
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Serial:",
                                                    className="font-weight-bold",
                                                    style=dict(
                                                        width="10ch",
                                                    ),
                                                ),
                                                data.get("serial"),
                                            ]
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Status:",
                                                    className="font-weight-bold",
                                                    style=dict(
                                                        width="10ch",
                                                    ),
                                                ),
                                                data.get("status", "").title(),
                                            ],
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "URL:",
                                                    className="font-weight-bold",
                                                    style=dict(
                                                        width="10ch",
                                                    ),
                                                ),
                                                html.A(
                                                    "link",
                                                    href=data.get("url", ""),
                                                    target="_blank",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                align="start",
                            ),
                        ]
                    )
                )
            ]

        super().__init__(
            children=children_,
            title=data.get("name"),
            is_open=True,
            placement="botton",
            class_name="w-100",
            **kwargs,
        )
