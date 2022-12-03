import datetime
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, TypedDict

import dash  # type: ignore
import dash_bootstrap_components as dbc  # type: ignore
import dash_extensions as de  # type: ignore
import dash_extensions.javascript as de_js  # type: ignore
from dash import dcc, html, Input, Output, State  # type: ignore
from dash.exceptions import PreventUpdate  # type: ignore
from dash_tabulator import DashTabulator  # type: ignore

from jenkins_query.pipeline_utils import get_downstream_serials, PipelineDict
from jenkins_query.viz.dash.partial_callback import PartialCallback


class LeftPane(dbc.Col):
    @dataclass
    class Callbacks:
        RefreshCallbackType = PartialCallback[Callable[..., Any]]
        refresh: RefreshCallbackType
        RefreshDataCallbackType = Callable[[], tuple[PipelineDict, dict]]
        refresh_data: RefreshDataCallbackType

    def __init__(self, app, pipeline_dict: PipelineDict, job_data: dict, callbacks: Callbacks):

        self.setup_refresh_callbacks(app, callbacks.refresh)
        self.setup_intvl_refresh_callback(app, callbacks.refresh)
        # self.setup_expand_all_callback(app)

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
                dbc.InputGroup(
                    [
                        dbc.InputGroupText(dbc.Label("Refresh every", align="end", class_name="my-0")),
                        dbc.Select(
                            id="sel-refresh-interval",
                            options=[
                                dict(label="1 min", value=60 * 1000),
                                dict(label="5 min", value=5 * 60 * 1000),
                                dict(label="10 mins", value=10 * 60 * 1000),
                            ],
                            value=5 * 60 * 1000,
                            persistence=True,
                        ),
                        dbc.InputGroupText(
                            dbc.Switch(id="cb-enable-refresh", persistence=True),
                        ),
                        dbc.Button(
                            html.I(className="bi-arrow-clockwise"),
                            id="btn-refresh-now",
                            className="btn btn-primary",
                        ),
                    ],
                ),
                html.Div(
                    [
                        html.Label(f"Last refresh:", className="me-1"),
                        html.Label(datetime.datetime.now().time().isoformat("seconds"), id="lbl-last-update"),
                        dcc.Interval(id="intvl-refresh", disabled=True),
                    ],
                ),
                html.Div(
                    [
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
                                "index": pipeline_dict["uuid"],
                            },
                            outline=True,
                            color="light",
                            class_name="m-1",
                            style={
                                "padding": "1px 2px 1px 2px",
                            },
                        ),
                        dbc.Button(
                            html.I(className="bi-chevron-expand", style={"font-size": "1rem"}),
                            id="btn-expand-all",
                            outline=True,
                            color="light",
                            class_name="m-1",
                            style={
                                "padding": "1px 2px 1px 2px",
                            },
                        ),
                        dcc.Interval(
                            id="intvl-expand-all",
                            interval=10,
                            disabled=True,
                        ),
                    ]
                ),
                # dbc.ListGroup(list(dbc.ListGroupItem(p) for p in job_details)),
                html.Div(
                    self.generate_jobs_table(self.generate_job_details(pipeline_dict, job_data), False),
                    id="div-jobs-table",
                ),
                de.EventListener(
                    id="el-diagram-click",
                    events=[dict(event="clickDiagramIcon", props=["detail"])],
                    logging=True,
                ),
                de.EventListener(
                    id="el-info-click",
                    events=[dict(event="clickInfoIcon", props=["detail"])],
                    logging=True,
                ),
            ),
            xxl=3,
            xl=4,
            lg=5,
            xs=12,
            id="col-left-pane",
        )

        self.setup_expand_all_callbacks(app)

    @classmethod
    def setup_expand_all_callbacks(cls, app: dash.Dash):
        expanded = False

        class TableCache(TypedDict):
            data: dict
            filtering: dict

        table_cache: TableCache = dict()

        @app.callback(
            Output("div-jobs-table", "children"),
            Output("intvl-expand-all", "max_intervals"),
            Output("intvl-expand-all", "disabled"),
            Input("btn-expand-all", "n_clicks"),
            State("jobs_table", "data"),
            State("jobs_table", "dataFiltering"),
            prevent_initial_call=True,
        )
        def expand_all(n_clicks: int, table_data, filtering) -> Any:
            nonlocal table_cache
            table_cache["data"] = table_data
            table_cache["filtering"] = filtering
            return [], 1, False

        @app.callback(
            Output("div-jobs-table", "children"),
            Output("intvl-expand-all", "disabled"),
            Output("intvl-expand-all", "n_intervals"),
            Input("intvl-expand-all", "n_intervals"),
            prevent_initial_call=True,
        )
        def delayed_table_gen(n_intvl):
            nonlocal expanded, table_cache
            expanded = not expanded
            return cls.generate_jobs_table(table_cache["data"], expanded, table_cache["filtering"]), True, 0

    @classmethod
    def generate_jobs_table(
        cls, table_data: list[dict], expand_all_: bool = False, filtering: Optional[list[dict]] = None
    ) -> DashTabulator:
        ns = de_js.Namespace("myNamespace", "tabulator")
        return DashTabulator(
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
                dict(
                    title="Serial",
                    field="serial",
                    headerFilter="input",
                    headerFilterFunc=ns("serialHeaderFilter"),
                    minWidth=120,
                    responsive=3,
                    widthGrow=1,
                ),
                dict(title="Time (UTC)", field="timestamp", minWidth=200, widthGrow=0, responsive=10),
                dict(
                    title="Status",
                    field="status",
                    formatter=ns("statusCellFormat"),
                    headerFilter="select",
                    headerFilterFunc=ns("statusHeaderFilter"),
                    headerFilterLiveFilter=False,
                    headerFilterParams=dict(
                        values=[
                            dict(
                                label="Clear Filter",
                                value="",
                                elementAttributes={"style": "color:#fff"},
                            ),
                            dict(
                                label="FAILURE",
                                value="FAILURE",
                                elementAttributes={"style": "color:#fff; background-color: #a23d32"},
                            ),
                            dict(
                                label="In Progress",
                                value="In Progress",
                                elementAttributes={"style": "color:#fff; background-color: #2d6e9a"},
                            ),
                            dict(
                                label="NOT RUN",
                                value="NOT RUN",
                                elementAttributes={"style": "color:#fff; background-color: #7c8187"},
                            ),
                            dict(
                                label="SUCCESS",
                                value="SUCCESS",
                                elementAttributes={"style": "color:#fff; background-color: #0b8667"},
                            ),
                            dict(
                                label="UNSTABLE",
                                value="UNSTABLE",
                                elementAttributes={"style": "color:#fff; background-color: #aa7117"},
                            ),
                        ],
                        multiselect=0,
                    ),
                    minWidth=100,
                    responsive=2,
                    widthGrow=1,
                ),
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
                    cellClick=ns("infoIconCellClick"),
                    cssClass="table-sm",
                    formatter=ns("infoIconColFormat"),
                    headerSort=False,
                    hozAlign="center",
                    resizable=False,
                    variableHeight=False,
                    width="40",
                    widthGrow=0,
                    widthShrink=0,
                ),
                dict(
                    cellClick=ns("diagramIconCellClick"),
                    cssClass="table-sm",
                    formatter=ns("diagramIconColFormat"),
                    headerSort=False,
                    hozAlign="center",
                    resizable=False,
                    variableHeight=False,
                    width="40",
                    widthGrow=0,
                    widthShrink=0,
                ),
            ],
            data=table_data,
            initialHeaderFilter=filtering,
            options=dict(
                dataTree=True,
                dataTreeChildColumnCalcs=True,
                dataTreeChildIndent=5,
                dataTreeFilter=True,
                dataTreeStartExpanded=expand_all_,
                layout="fitColumns",
                responsiveLayout="hide",
                rowClick=ns("rowClick"),
                # rowFormatter=ns("rowFormat"),
            ),
            theme="tabulator_midnight",
        )

    @classmethod
    def generate_job_details(cls, pipeline_dict, job_data):
        job_details = []
        for name, data in pipeline_dict["children"].items():
            job_details += add_jobs_to_table(
                name=name,
                job_struct=data,
                job_data=job_data,
            )
        return job_details

    @classmethod
    def setup_refresh_callbacks(cls, app: dash.Dash, callback: Callbacks.RefreshCallbackType) -> None:
        @app.callback(
            Output("intvl-refresh", "disabled"),
            Output("intvl-refresh", "interval"),
            Input("cb-enable-refresh", "value"),
            Input("sel-refresh-interval", "value"),
        )
        def enable_refresh(cb_value: bool, interval: int) -> tuple[bool, int]:
            return not cb_value, int(interval)

        @app.callback(
            *callback.outputs,
            Output("lbl-last-update", "children"),
            Input("btn-refresh-now", "n_clicks"),
            *callback.inputs,
            prevent_initial_call=True,
        )
        def refresh_now(n_clicks: int, *args, **kwargs) -> Any:
            current_time = datetime.datetime.now().time().isoformat("seconds")
            return *callback.function(*args, **kwargs), current_time

    @classmethod
    def setup_intvl_refresh_callback(cls, app: dash.Dash, callback: Callbacks.RefreshCallbackType) -> None:
        @app.callback(
            output=callback.outputs
            + [
                Output("lbl-last-update", "children"),
            ],
            inputs=callback.inputs + [Input("intvl-refresh", "n_intervals")],
            prevent_initial_call=True,
        )
        def intvl_refresh_trigger(nintervals, *args, **kwargs):
            if not dash.ctx.triggered_id == "intvl-refresh":
                raise PreventUpdate()
            current_time = datetime.datetime.now().time().isoformat("seconds")
            return *callback.function(*args, **kwargs), current_time


def add_jobs_to_table(name: str, job_struct: PipelineDict, job_data: dict, indent=1) -> List[dict]:
    details: dict = dict(
        _children=[],
    )
    status_color_map = defaultdict(
        lambda: "#7c8187",
        {
            "FAILURE": "#a23d32",
            "SUCCESS": "#0b8667",
            "UNSTABLE": "#aa7117",
            "In Progress": "#2d6e9a",
            None: "#2d6e9a",
        },
    )
    if "server" in job_struct:
        fields = job_data[name]
        details.update(
            dict(
                name=fields["name"],
                serial=fields["serial"],
                build_num=fields["build_num"],
                timestamp=fields["timestamp"].strftime("%y-%m-%d %H:%M UTC") if fields["timestamp"] else None,
                status=fields["status"],
                url=fields["url"],
                num_children=len(job_struct["children"]),
            )
        )
    else:
        details.update(
            dict(
                name=name,
                serial=sorted(get_downstream_serials(job_struct, job_data)),
                status=job_struct.get("downstream_status", None),
            )
        )
    details.update(
        dict(
            _color=status_color_map[job_data.get(name, {}).get("status") or job_struct.get("downstream_status")],
            _uuid=job_struct["uuid"],
        )
    )

    for next_name in job_struct["children"]:
        children = add_jobs_to_table(
            name=next_name,
            job_struct=job_struct["children"][next_name],
            job_data=job_data,
            indent=indent + 1,
        )
        details["_children"] += children

    if not details["_children"]:
        details["_children"] = None

    return [details]
