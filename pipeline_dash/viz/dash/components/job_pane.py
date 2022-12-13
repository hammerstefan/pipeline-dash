# intended to be the bottom of screen job info pane
from dataclasses import dataclass
from typing import Optional

import dash_bootstrap_components as dbc  # type: ignore
from dash import dash, html, Input, Output  # type: ignore


class JobPane(dbc.Offcanvas):
    @dataclass
    class Data:
        name: str
        serial: Optional[str | list[str]]
        status: str
        url: Optional[str]
        uuid: str

    class Ids:
        button_diagram = "btn-job-pane-diagram"
        id = "offcanvas-job-pane"

    ids = Ids

    def __init__(self, app: dash.Dash, data: Data, **kwargs):
        children_ = []
        if data:
            children_ = [
                dbc.Card(dbc.Container([self._layout_data(data)])),
                dash.dcc.Store(id="store-job-pane-uuid", data=data.uuid),
            ]

        super().__init__(
            children=children_,
            id=self.ids.id,
            title=data.name,
            is_open=True,
            placement="botton",
            class_name="w-100",
            **kwargs,
        )

    @classmethod
    def _layout_data(cls, data: Data) -> dbc.Row:
        return dbc.Row(
            [
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.Label("Serial:", className="font-weight-bold", style={"width": "10ch"}),
                                ", ".join(data.serial) if isinstance(data.serial, list) else data.serial,
                            ]
                        ),
                        html.Div(
                            [
                                html.Label("Status:", className="font-weight-bold", style={"width": "10ch"}),
                                data.status.title(),
                            ],
                        ),
                        html.Div(
                            [
                                html.Label("URL:", className="font-weight-bold", style={"width": "10ch"}),
                                html.A("link", href=data.url, target="_blank"),
                            ],
                        ),
                    ],
                ),
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.Label("UUID:", className="font-weight-bold", style={"width": "10ch"}),
                                data.uuid,
                            ]
                        )
                    ]
                ),
                dbc.Col(
                    [
                        # html.A("View Subgraph", id=cls.ids.button_diagram, href="#"),
                        # dbc.Button(html.I(className="bi-diagram-2"), id=cls.ids.button_diagram),
                    ]
                ),
            ],
            align="start",
        )
