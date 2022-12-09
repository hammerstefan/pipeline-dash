# intended to be the bottom of screen job info pane
from dataclasses import dataclass
from typing import Optional

import dash_bootstrap_components as dbc  # type: ignore
from dash import html  # type: ignore


class JobPane(dbc.Offcanvas):
    @dataclass
    class Data:
        name: str
        serial: Optional[str | list[str]]
        status: str
        url: Optional[str]

    def __init__(self, data: Data, **kwargs):
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
                                                ", ".join(data.serial)
                                                if isinstance(data.serial, list)
                                                else data.serial,
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
                                                data.status.title(),
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
                                                    href=data.url,
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
            title=data.name,
            is_open=True,
            placement="botton",
            class_name="w-100",
            **kwargs,
        )
