from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

import dash  # type: ignore
import dash_bootstrap_components as dbc  # type: ignore
from dash import ALL, html, Input, MATCH, Output, State  # type: ignore

# import dash_extensions.enrich as de
from dash.dcc import Store  # type: ignore
from dash.exceptions import PreventUpdate  # type: ignore

from pipeline_dash.viz.dash.logged_callback import logged_callback
from pipeline_dash.viz.dash.partial_callback import PartialCallback


class ButtonSplitOption(html.Div):
    @dataclass
    class Store:
        options: List
        label: str
        index: int

    @dataclass
    class Output:
        n_clicks: int
        index: int

    class Ids:
        button = lambda aio_id: dict(
            component="ButtonSplitOption",
            subcomponent="button",
            aio_id=aio_id,
        )
        dropdown = lambda aio_id: dict(
            component="ButtonSplitOption",
            subcomponent="dropdown",
            aio_id=aio_id,
        )
        dropdown_item = lambda aio_id, index: dict(
            component="ButtonSplitOption",
            subcomponent="dropdown_item",
            aio_id=aio_id,
            index=index,
        )
        store = lambda aio_id: dict(
            component="ButtonSplitOption",
            subcomponent="store",
            aio_id=aio_id,
        )
        output = lambda aio_id: dict(
            component="ButtonSplitOption",
            subcomponent="output",
            aio_id=aio_id,
        )

    ids = Ids

    CallbackType = PartialCallback[Callable[[Output], Any]]

    def __init__(
        self,
        app,
        callback: CallbackType | None,
        label: str = "",
        options: Optional[list] = None,
        inital_index: int = 0,
        aio_id: Optional[str] = None,
    ):
        options = options or []
        aio_id = aio_id or str(uuid.uuid4())
        self.index = inital_index
        self.dropdown_items = [
            dbc.DropdownMenuItem(
                opt,
                id=self.ids.dropdown_item(aio_id, i),
            )
            for i, opt in enumerate(options)
        ]
        super().__init__(
            [
                dbc.Button(
                    f"{label} {options[inital_index]}",
                    id=self.ids.button(aio_id),
                    class_name="pe-1",
                ),
                dbc.DropdownMenu(
                    self.dropdown_items,
                    id=self.ids.dropdown(aio_id),
                    class_name="btn-group me-1",
                ),
                Store(
                    id=self.ids.store(aio_id),
                    data=self.Store(
                        options=options,
                        label=label,
                        index=inital_index,
                    ),
                ),
                Store(
                    id=self.ids.output(aio_id),
                    data=self.Output(
                        n_clicks=0,
                        index=inital_index,
                    ),
                ),
            ],
            className="btn-group",
        )

        @app.callback(
            [
                dash.Output(self.ids.store(MATCH), "data"),
                dash.Output(self.ids.button(MATCH), "children"),
            ],
            Input(self.ids.dropdown_item(MATCH, ALL), "n_clicks"),
            State(self.ids.button(MATCH), "children"),
            State(self.ids.store(MATCH), "data"),
            State(self.ids.output(MATCH), "data"),
            prevent_initial_call=True,
        )
        @logged_callback
        def cb_btn_click(nclicks_dd, btn_children, store, output) -> Tuple[Store, str]:
            cid = dash.ctx.triggered_id
            store = ButtonSplitOption.Store(**store)
            output = ButtonSplitOption.Output(**output)
            if cid["subcomponent"] == ButtonSplitOption.ids.dropdown_item(MATCH, ALL)["subcomponent"]:
                store.index = cid["index"]
                btn_children = [f"{store.label} {store.options[store.index]}"]
            return store, btn_children

        if callback:

            @app.callback(
                output=callback.outputs + [dash.Output(self.ids.output(aio_id), "data")],
                inputs=dict(
                    data=(
                        Input(self.ids.button(aio_id), "n_clicks"),
                        State(self.ids.store(aio_id), "data"),
                    ),
                    callback_inputs=callback.inputs,
                ),
                prevent_initial_call=True,
            )
            @logged_callback
            def btn_refresh(data, callback_inputs) -> Output | tuple[Any, Output]:
                # todo combine this callback with the main callback
                if not dash.ctx.triggered_id == self.ids.button(aio_id):
                    raise PreventUpdate()
                nclicks = data[0]
                store = ButtonSplitOption.Store(**data[1])
                output = ButtonSplitOption.Output(n_clicks=nclicks, index=store.index)
                return *(callback.function(output, *callback_inputs) if callback else []), output
