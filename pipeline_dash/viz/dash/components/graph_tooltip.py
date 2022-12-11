from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Callable, ClassVar, Optional, TypedDict

import dash_bootstrap_components as dbc  # type: ignore
from dash import dash, dcc, html, Input, Output, State  # type: ignore
from dash.exceptions import PreventUpdate  # type: ignore

from pipeline_dash.viz.dash import components, viz_dash
from pipeline_dash.viz.dash.partial_callback import PartialCallback

StyleType = dict[str, Any]
DataStoreType = dict[str, Any]


class GraphTooltip(html.Span):
    class Ids:
        class ButtonIds:
            open_jenkins = "tooltip-btn-open-jenkins"
            view_subgraph = "tooltip-btn-view-subgraph"
            view_details = "tooltip-btn-view-details"
            close = "tooltip-btn-close"

        class StoreIds:
            node_data = "tooltip-store-node-data"

        id = "tooltip-pipeline-graph"
        buttons = ButtonIds
        stores = StoreIds

    ids = Ids

    @dataclass
    class Data:
        name: str
        serial: Optional[str | list[str]]
        status: str
        url: Optional[str]
        uuid: str

    class Bbox(TypedDict):
        x0: float
        x1: float
        y0: float
        y2: float

    @staticmethod
    def cb_display(bbox: Bbox, data: Data, style: StyleType) -> tuple[StyleType, DataStoreType, Optional[str]]:
        style.update({"visibility": "visible", "left": bbox["x1"], "top": mean([bbox["y0"], bbox["y0"]])})
        return style, asdict(data), data.url

    DisplayCallbackType = PartialCallback[Callable[[Bbox, Data, dict], Any]]

    @dataclass
    class InCallbacks:
        display: GraphTooltip.DisplayCallbackType

    callbacks: ClassVar[InCallbacks]

    def __init__(self, app: dash.Dash, **kwargs):
        super().__init__(
            self._children(),
            id=self.ids.id,
            style={
                "visibility": "hidden",
                "background-color": "var(--bs-body-bg)",
                "color": "var(--bs-body-color)",
                "border-style": "solid",
                "border-width": "1px",
                "border-color": "var(--bs-secondary)",
                "text-align": "left",
                "position": "absolute",
                "z-index": "10",
                "padding": "2px",
                "margin-left": "5x",
                "border-radius": "2px",
                "left": "0",
            },
            **kwargs,
        )
        self.setup_callbacks(app)

    def _children(self) -> list:
        return [
            html.I(
                className="bi bi-x",
                id=self.ids.buttons.close,
                style={
                    "font-size": "1.5rem",
                    "position": "absolute",
                    "top": "-5px",
                    "right": "0",
                },
            ),
            html.Div(
                [
                    html.Div(html.A("Open Jenkins", id=self.ids.buttons.open_jenkins, href="#", target="_blank")),
                    html.Div(html.A("View Subgraph", id=self.ids.buttons.view_subgraph, href="#")),
                    html.Div(html.A("View Details", id=self.ids.buttons.view_details, href="#")),
                ],
                style={
                    "margin-right": "2em",
                }
                # className="ps-1",
            ),
            dcc.Store(id=self.ids.stores.node_data),
        ]

    def setup_callbacks(self, app: dash.Dash) -> None:
        @app.callback(
            Output(self.ids.id, "style"),
            inputs=[
                (
                    Input(self.ids.buttons.close, "n_clicks"),
                    Input(self.ids.buttons.open_jenkins, "n_clicks"),
                    Input(self.ids.buttons.view_subgraph, "n_clicks"),
                    Input(self.ids.buttons.view_details, "n_clicks"),
                ),
                State(self.ids.id, "style"),
            ],
            prevent_initial_call=True,
        )
        def cb_btn_close_clicked(n_clicks, style):
            if all(nc is None for nc in n_clicks):
                raise PreventUpdate()
            style.update({"visibility": "hidden"})
            return style

        @app.callback(
            Output(viz_dash.Ids.stores.figure_root, "data"),
            Input(self.ids.buttons.view_subgraph, "n_clicks"),
            State(self.ids.stores.node_data, "data"),
            prevent_initial_call=True,
        )
        def cb_btn_view_subgraph_clicked(n_clicks, node_data):
            if n_clicks is None:
                raise PreventUpdate()
            node_data = self.Data(**node_data)
            return node_data.uuid

        @app.callback(
            Output(viz_dash.Ids.stores.job_pane_data, "data"),
            Input(self.ids.buttons.view_details, "n_clicks"),
            State(self.ids.stores.node_data, "data"),
            prevent_initial_call=True,
        )
        def cb_btn_view_details_clicked(n_clicks, data):
            if n_clicks is None:
                raise PreventUpdate()
            data = self.Data(**data)
            data = components.JobPane.Data(**asdict(data))
            return asdict(data)


GraphTooltip.callbacks = GraphTooltip.InCallbacks(
    display=PartialCallback(
        inputs=[
            State(GraphTooltip.ids.id, "style"),
        ],
        outputs=[
            Output(GraphTooltip.ids.id, "style"),
            Output(GraphTooltip.ids.stores.node_data, "data"),
            Output(GraphTooltip.ids.buttons.open_jenkins, "href"),
        ],
        function=GraphTooltip.cb_display,
    )
)
