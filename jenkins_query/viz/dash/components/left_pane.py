from collections import defaultdict
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, List

import dash  # type: ignore
import dash_bootstrap_components as dbc  # type: ignore
import dash_extensions as de  # type: ignore
import dash_extensions.javascript as de_js  # type: ignore
from dash import dcc, html, Input, Output  # type: ignore
from dash.exceptions import PreventUpdate  # type: ignore
from dash_tabulator import DashTabulator  # type: ignore

from .. import components
from ..partial_callback import PartialCallback


class LeftPane(dbc.Col):
    @dataclass
    class Callbacks:
        RefreshCallbackType = PartialCallback[Callable[..., Any]]
        refresh: RefreshCallbackType

    def __init__(self, app, pipeline_dict, job_data, callbacks: Callbacks):
        job_details = []
        for name, data in pipeline_dict.items():
            if name.startswith("__") and name.endswith("__"):
                continue
            job_details += add_jobs_to_table(
                name=name,
                job_struct=data,
                job_data=job_data,
            )

        callback_refresh = self.gen_refresh_callback(callbacks.refresh)
        self.setup_intvl_refresh_callback(app, callbacks.refresh)

        ns = de_js.Namespace("myNamespace", "tabulator")
        super().__init__(
            (
                html.Header(
                    [
                        html.H3("Jenkins Job Table"),
                        dbc.Button(
                            html.I(className="bi-arrows-angle-expand"),
                            id="btn-left-pane-expand",
                            color="light",
                        ),
                    ],
                    className="d-flex justify-content-between align-items-center",
                ),
                html.Div(
                    [
                        components.aio.ButtonSplitOption(
                            app,
                            label="Refresh",
                            options=[
                                "Once",
                                "Every 1 min",
                                "Every 10 min",
                            ],
                            aio_id="btn-refresh",
                            callback=callback_refresh,
                        ),
                        dcc.Interval(
                            id="intvl-refresh",
                            disabled=True,
                        ),
                        dbc.Switch(
                            label="Responsive",
                            id="cb-responsive-graph",
                            value=True,
                            className="m-2",
                            style=dict(
                                display="inline-block",
                            ),
                        ),
                        html.Div([], id="div-test"),
                        dbc.Button(
                            html.I(className="bi-diagram-2", style={"font-size": "1rem"}),
                            id={
                                "type": "btn-diagram",
                                "index": pipeline_dict["__uuid__"],
                            },
                            outline=True,
                            color="secondary",
                            class_name="m-1",
                            style={
                                "padding": "1px 2px 1px 2px",
                            },
                        ),
                        dbc.Button(
                            html.I(className="bi-chevron-expand", style={"font-size": "1rem"}),
                            id={"type": "btn-expand", "index": pipeline_dict["__uuid__"]},
                            outline=True,
                            color="secondary",
                            class_name="m-1",
                            style={
                                "padding": "1px 2px 1px 2px",
                            },
                        ),
                    ]
                ),
                # dbc.ListGroup(list(dbc.ListGroupItem(p) for p in job_details)),
                DashTabulator(
                    id="jobs_table",
                    columns=[
                        dict(
                            field="name",
                            headerFilter="input",
                            headerFilterFunc=ns("nameHeaderFilter"),
                            minWidth=200,
                            responsive=0,
                            title="Name",
                            widthGrow=3,
                        ),
                        dict(title="Serial", field="serial", minWidth=120, widthGrow=0, responsive=3),
                        # dict(title="No.", field="build_num"),
                        dict(title="Time (UTC)", field="timestamp", minWidth=200, widthGrow=0, responsive=10),
                        dict(title="Status", field="status", minWidth=90, widthGrow=1, responsive=2),
                        dict(
                            title="Job",
                            field="url",
                            formatter="link",
                            formatterParams=dict(
                                labelField="build_num",
                                target="_blank",
                            ),
                            width=65,
                            widthGrow=0,
                        ),
                        dict(
                            formatter=ns("diagramIconColFormat"),
                            width=40,
                            hozAlign="center",
                            headerSort=False,
                            cellClick=ns("diagramIconCellClick"),
                            cssClass="table-sm",
                            variableHeight=False,
                        ),
                    ],
                    data=job_details,
                    options=dict(
                        dataTree=True,
                        dataTreeChildColumnCalcs=True,
                        dataTreeChildIndent=5,
                        dataTreeFilter=True,
                        layout="fitColumns",
                        responsiveLayout="hide",
                        rowClick=ns("rowClick"),
                        rowFormatter=ns("rowFormat"),
                    ),
                    theme="bootstrap/tabulator_bootstrap4",
                ),
                de.EventListener(
                    id="el-diagram-click",
                    events=[dict(event="clickDiagramIcon", props=["detail"])],
                    logging=True,
                ),
            ),
            xxl=3,
            xl=4,
            lg=5,
            xs=12,
            id="col-left-pane",
        )

    @classmethod
    def gen_refresh_callback(
        cls, callback: Callbacks.RefreshCallbackType
    ) -> components.aio.ButtonSplitOption.CallbackType:
        def callback_refresh_fn(n: components.aio.ButtonSplitOption.Output, *args, **kwargs):
            time_map = [
                0,
                60 * 1000,
                10 * 60 * 1000,
            ]
            interval = time_map[n.index]
            disabled = False if interval else True
            return callback.function(*args, **kwargs), disabled, interval

        callback_refresh: components.aio.ButtonSplitOption.CallbackType = PartialCallback(
            outputs=callback.outputs
            + [
                Output("intvl-refresh", "disabled"),
                Output("intvl-refresh", "interval"),
            ],
            inputs=callback.inputs,
            function=callback_refresh_fn,
        )
        return callback_refresh

    @classmethod
    def setup_intvl_refresh_callback(cls, app: dash.Dash, callback: Callbacks.RefreshCallbackType) -> None:
        @app.callback(
            output=callback.outputs,
            inputs=callback.inputs + [Input("intvl-refresh", "n_intervals")],
            prevent_initial_call=True,
        )
        def intvl_refresh_trigger(nintervals, *args, **kwargs):
            if not dash.ctx.triggered_id == "intvl-refresh":
                raise PreventUpdate()
            return callback.function(*args, **kwargs)


def add_jobs_to_table(name: str, job_struct: dict, job_data: dict, indent=1) -> List[dict]:
    details: dict = dict(
        _children=[],
    )
    status_classname_map = defaultdict(
        lambda: "table-dark",
        {
            "FAILURE": "table-danger",
            "SUCCESS": "table-success",
            "UNSTABLE": "table-warning",
            "In Progress": "table-info",
            None: "table-info",
        },
    )
    if "__server__" in job_struct:
        fields = job_data[name]
        details.update(
            dict(
                name=fields["name"],
                serial=fields["serial"],
                build_num=fields["build_num"],
                timestamp=fields["timestamp"].strftime("%y-%m-%d %H:%M UTC") if fields["timestamp"] else None,
                status=fields["status"],
                url=fields["url"],
                num_children=len([n for n in job_struct if not n.startswith("__") and not n.endswith("__")])
                # html.Span([
                #     dbc.Button(
                #         html.I(className="bi-chevron-expand", style={"font-size": "1rem"}),
                #         id={
                #             "type": "btn-expand",
                #             "index": job_struct['__uuid__'],
                #         },
                #         outline=True,
                #         color="secondary",
                #         class_name="m-1",
                #         style={"padding": "1px 2px 1px 2px", }
                #     ), ],
                #     style={
                #         "min-width": "68px",
                #     },
                # )
            )
        )
        # if fields["timestamp"] and datetime.now() - fields["timestamp"] > timedelta(hours=24):
        #     table.rows[-1].style = "dim"
    else:
        details.update(
            dict(
                name=name,
                serial=None,
                status=job_struct.get("__downstream_status__", None),
                # html.Span([
                #     dbc.Button(
                #         html.I(className="bi-chevron-expand", style={"font-size": "1rem"}),
                #         id={
                #             "type": "btn-expand",
                #             "index": job_struct['__uuid__'],
                #         },
                #         outline=True,
                #         color="secondary",
                #         class_name="m-1",
                #         style={"padding": "1px 2px 1px 2px", }
                #     ), ],
                #     style={
                #         "min-width": "68px",
                #     }
                # ),
                #
            )
        )
    details.update(
        dict(
            _class=status_classname_map[job_struct.get("__downstream_status__", None)],
            _uuid=job_struct["__uuid__"],
        )
    )

    for next_name in job_struct:
        if next_name.startswith("__") and next_name.endswith("__"):
            continue
        children = add_jobs_to_table(
            name=next_name,
            job_struct=job_struct[next_name],
            job_data=job_data,
            indent=indent + 1,
        )
        details["_children"] += children

    if not details["_children"]:
        details["_children"] = None

    return [details]
