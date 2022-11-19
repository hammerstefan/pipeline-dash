from collections import defaultdict
from typing import Tuple, List

import dash_bootstrap_components as dbc
from dash import html


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
        job_details.append(job_children)
        btn_list += btn_list_
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
                        )
                    ],
                    className="d-flex justify-content-between align-items-center",
                ),
                html.Div([
                    dbc.Button(
                        "Test",
                        id="btn-test"
                    ),
                    html.Div([], id="div-test"),
                    dbc.Button(
                        html.I(className="bi-diagram-2", style={"font-size": "1rem"}),
                        id={
                            "type": "btn-diagram",
                            "index": pipeline_dict['__uuid__'],
                        },
                        outline=True,
                        color="secondary",
                        class_name="m-1",
                        style={"padding": "1px 2px 1px 2px", }
                    ),
                    dbc.Button(
                        html.I(className="bi-chevron-expand", style={"font-size": "1rem"}),
                        id={
                            "type": "btn-expand",
                            "index": pipeline_dict['__uuid__']
                        },
                        outline=True,
                        color="secondary",
                        class_name="m-1",
                        style={"padding": "1px 2px 1px 2px", }
                    ),
                ]),
                dbc.ListGroup(list(dbc.ListGroupItem(p) for p in job_details)),
            ),
            xxl=3, xl=4, lg=5, xs=12,
            id="col-left-pane"
        ),
        btn_list
    )


def add_jobs_to_table(name: str,
                      job_struct: dict,
                      job_data: dict,
                      indent=1) -> Tuple[html.Details, List[dbc.Button]]:
    details = html.Details(
        children=[],
        id={
            "type": "details-job",
            "index": job_struct['__uuid__'],
        },
        className="details-job border",
        style={
            "text-indent": f"{indent*.5}em",
        }
    )
    status_classname_map = defaultdict(lambda: "alert-dark", {
        "FAILURE": "alert-danger",
        "SUCCESS": "alert-success",
        "UNSTABLE": "alert-warning",
        "In Progress": "alert-info",
        None: "alert-info",
        "default": "alert-dark",
    })
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
                style={"padding": "1px 2px 1px 2px", }
            )
        )
        details.children.append(html.Summary(
            [
                html.Span(
                    fields["name"],
                    style={
                        "font-size": ".75rem",
                        "flex-grow": "1",
                    },
                ),
                html.Span(
                    fields["serial"],
                    style={"font-size": ".75rem", },
                ),
                html.Span(
                    [""],
                    style={
                        # "display": "inline-block",
                        # "width": "max-content",
                    },
                ),
                html.Span([
                    btn_diagram_list[-1],
                    dbc.Button(
                        html.I(className="bi-chevron-expand", style={"font-size": "1rem"}),
                        id={
                            "type": "btn-expand",
                            "index": job_struct['__uuid__'],
                        },
                        outline=True,
                        color="secondary",
                        class_name="m-1",
                        style={"padding": "1px 2px 1px 2px", }
                    ), ],
                    style={
                        "min-width": "68px",
                    },
                )
            ],
            className=f"{status_classname_map[job_struct.get('__downstream_status__', None)]} "
                      "d-flex justify-content-between align-items-center flex-wrap",
            style={
            }
        ))
        # table.add_row(
        #     prefix + fields["name"],
        #     fields["serial"],
        #     fields["build_num"],
        #     fields["timestamp"].strftime("%y-%m-%d %H:%M UTC") if fields["timestamp"] else None ,
        #     status(fields["status"]),
        #     fields["url"],
        #     )
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
                style={"padding": "1px 2px 1px 2px", }
            )
        )
        details.children.append(html.Summary(
            [
                html.Span(
                    name,
                    style={
                        # "margin-left": "-0.3em",
                        "flex-grow": "1",
                    }
                ),
                html.Span([
                    btn_diagram_list[-1],
                    dbc.Button(
                        html.I(className="bi-chevron-expand", style={"font-size": "1rem"}),
                        id={
                            "type": "btn-expand",
                            "index": job_struct['__uuid__'],
                        },
                        outline=True,
                        color="secondary",
                        class_name="m-1",
                        style={"padding": "1px 2px 1px 2px", }
                    ), ],
                    style={
                        "min-width": "68px",
                    }
                ),

            ],
            className=f"{status_classname_map[job_struct.get('__downstream_status__', None)]} "
                      "d-flex justify-content-between flex-wrap",
            style={
                "display": "revert",
                # "width": "calc(100% - 1.1em)",
                # "margin-left": "3em",
            }
        ))

    d = html.Div(
        children=[],
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
        d.children.append(children)
        btn_diagram_list += btn_list
    details.children.append(d)

    return details, btn_diagram_list