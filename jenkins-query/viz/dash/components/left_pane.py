from collections import defaultdict
from typing import List, Tuple

import dash_bootstrap_components as dbc
import dash_extensions as de
import dash_extensions.javascript as de_js
from dash import html
from dash_tabulator import DashTabulator


def generate(pipeline_dict, job_data) -> Tuple[dbc.Col, List[dbc.Button]]:
    job_details = []
    btn_list = []
    for name, data in pipeline_dict.items():
        if name.startswith("__") and name.endswith("__"):
            continue
        job_children, btn_list_ = add_jobs_to_table(
            name=name,
            job_struct=data,
            job_data=job_data,
        )
        job_details += job_children
        btn_list += btn_list_
    ns = de_js.Namespace("myNamespace", "tabulator")
    return (
        dbc.Col(
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
                        dbc.Button("Test", id="btn-test"),
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
                        dataTreeFilter=True,
                        dataTreeChildColumnCalcs=True,
                        dataTreeChildIndent=5,
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
        ),
        btn_list,
    )


def add_jobs_to_table(name: str, job_struct: dict, job_data: dict, indent=1) -> Tuple[List[dict], List[dbc.Button]]:
    details = dict(
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
    btn_diagram_list = []
    if "__server__" in job_struct:
        btn_diagram_list.append(f"btn-diagram-{job_struct['__uuid__']}")
        fields = job_data[name]
        btn_diagram_list.append(
            dbc.Button(
                html.I(className="bi-diagram-2", style={"font-size": "1rem"}),
                id=f"btn-diagram-{job_struct['__uuid__']}",
                outline=True,
                color="secondary",
                class_name="m-1",
                style={
                    "padding": "1px 2px 1px 2px",
                },
            )
        )
        details.update(
            dict(
                name=fields["name"],
                serial=fields["serial"],
                build_num=fields["build_num"],
                timestamp=fields["timestamp"].strftime("%y-%m-%d %H:%M UTC") if fields["timestamp"] else None,
                status=fields["status"],
                url=fields["url"],
                # html.Span([
                #     btn_diagram_list[-1],
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
        btn_diagram_list.append(
            dbc.Button(
                html.I(className="bi-diagram-2", style={"font-size": "1rem"}),
                id=f"btn-diagram-{job_struct['__uuid__']}",
                outline=True,
                color="secondary",
                class_name="m-1",
                style={
                    "padding": "1px 2px 1px 2px",
                },
            )
        )
        details.update(
            dict(
                name=name,
                serial=None,
                status=job_struct.get("__downstream_status__", None),
                # html.Span([
                #     btn_diagram_list[-1],
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
        children, btn_list = add_jobs_to_table(
            name=next_name,
            job_struct=job_struct[next_name],
            job_data=job_data,
            indent=indent + 1,
        )
        details["_children"] += children
        btn_diagram_list += btn_list

    if not details["_children"]:
        details["_children"] = None

    return [details], btn_diagram_list
