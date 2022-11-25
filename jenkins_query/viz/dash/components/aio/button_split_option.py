from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pprint import pprint
from typing import Any, Callable, List, Optional, Tuple

import dash  # type: ignore
from dash import ALL, html, Input, MATCH, Output, State  # type: ignore
import dash_bootstrap_components as dbc  # type: ignore

# import dash_extensions.enrich as de
from dash.dcc import Store  # type: ignore
from dash.exceptions import PreventUpdate

from jenkins_query.viz.dash.partial_callback import PartialCallback


class ButtonSplitOption(html.Div):
    @dataclass
    class Store:
        options: List

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
                    label,
                    id=self.ids.button(aio_id),
                    class_name="pe-1",
                ),
                dbc.DropdownMenu(
                    self.dropdown_items,
                    label=options[inital_index] if options else None,
                    id=self.ids.dropdown(aio_id),
                    class_name="btn-group",
                ),
                Store(
                    id=self.ids.store(aio_id),
                    data=self.Store(options=options),
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
                dash.dependencies.Output(self.ids.output(MATCH), "data"),
                dash.dependencies.Output(self.ids.store(MATCH), "data"),
                dash.dependencies.Output(self.ids.dropdown(MATCH), "label"),
            ],
            Input(self.ids.dropdown_item(MATCH, ALL), "n_clicks"),
            Input(self.ids.button(MATCH), "n_clicks"),
            State(self.ids.dropdown(MATCH), "label"),
            State(self.ids.store(MATCH), "data"),
            State(self.ids.output(MATCH), "data"),
            prevent_initial_call=True,
        )
        def btn_click(nclicks_dd, nclicks_btn, label, store, output) -> Tuple[dict, dict, str]:
            cid = dash.ctx.triggered_id
            store = ButtonSplitOption.Store(**store)
            output = ButtonSplitOption.Output(**output)
            if cid["subcomponent"] == ButtonSplitOption.ids.dropdown_item(MATCH, ALL)["subcomponent"]:
                output.index = cid["index"]
                label = store.options[output.index]
            output.n_clicks = int(output.n_clicks) + 1
            return asdict(output), asdict(store), label

        if callback:

            @app.callback(
                output=callback.outputs,
                inputs=dict(
                    data=(Input(self.ids.output(aio_id), "data")),
                    callback_inputs=callback.inputs,
                ),
                prevent_initial_call=True,
            )
            def btn_refresh(data, callback_inputs):
                if not dash.ctx.triggered_id == self.ids.output(aio_id):
                    raise PreventUpdate()
                data = ButtonSplitOption.Output(**data)
                return callback.function(data, *callback_inputs)
