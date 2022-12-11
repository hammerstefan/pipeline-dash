import json
import time
from dataclasses import asdict, dataclass
from importlib.resources import files
from typing import Callable, Optional

import dash  # type: ignore
import dash_bootstrap_components as dbc  # type: ignore
import dash_bootstrap_templates  # type: ignore
import diskcache
import plotly  # type: ignore
from dash import ALL, dcc, html, Input, Output, State  # type: ignore
from dash.exceptions import PreventUpdate  # type: ignore
from dash_extensions import enrich as de  # type: ignore
from plotly import graph_objects as go  # type: ignore

import pipeline_dash.viz.dash.components.jobs_pipeline_fig
from pipeline_dash.job_data import JobData, JobDataDict
from pipeline_dash.pipeline_utils import find_pipeline, PipelineDict, translate_uuid
from . import components, network_graph
from .components.job_pane import JobPane
from .network_graph import generate_nx
from .partial_callback import PartialCallback


class Ids:
    class StoreIds:
        figure_root = "store-figure-root"
        job_pane_data = "store-job-pane-date"

    stores = StoreIds


@dataclass
class Config:
    debug: bool = False


def display_dash(get_job_data_fn: Callable[[], tuple[PipelineDict, JobDataDict]], config: Config):

    cache = diskcache.Cache("./.diskcache")  # type: ignore
    background_callback_manager = dash.DiskcacheManager(cache)
    pipeline_dict, job_data = get_job_data_fn()
    graph = generate_nx(pipeline_dict, job_data)
    app = de.DashProxy(
        __name__,
        external_stylesheets=[
            # dbc.themes.DARKLY,
            dbc.icons.BOOTSTRAP,
        ],
        transforms=[
            de.TriggerTransform(),
            de.MultiplexerTransform(),
            de.NoOutputTransform(),
            # de.OperatorTransform(),
        ],
        meta_tags=[
            # dict(name="color-scheme", content="only light"),
        ],
        assets_ignore="tabulator_.*css",
    )
    dash_bootstrap_templates.load_figure_template("darkly")

    def callback_refresh(figure_root) -> tuple[go.Figure, list[dict], str]:
        nonlocal pipeline_dict, job_data
        # TODO: don't regen the world just to refresh some data from Jenkins
        print(f"CALLBACK {figure_root}")
        pipeline_dict_new, job_data_new = get_job_data_fn()
        if rv := translate_uuid(figure_root, pipeline_dict, pipeline_dict_new):
            figure_root, sub_dict = rv
            print(f"Sub dict found: True")
        else:
            sub_dict = pipeline_dict_new
            print(f"Sub dict found: False")
        graph_ = generate_nx(sub_dict, job_data_new)
        fig_ = components.jobs_pipeline_fig.generate_plot_figure(graph_)
        table_data = components.LeftPane.generate_job_details(pipeline_dict_new, job_data_new)
        pipeline_dict, job_data = pipeline_dict_new, job_data_new  # update the class pipeline/data cache
        return fig_, table_data, figure_root

    callback: components.LeftPane.Callbacks.RefreshCallbackType = PartialCallback(
        outputs=[
            Output("pipeline-graph", "figure"),
            Output("jobs_table", "data"),
            Output(Ids.stores.figure_root, "data"),
        ],
        inputs=[State(Ids.stores.figure_root, "data")],
        function=callback_refresh,
    )

    left_pane = components.LeftPane(
        app,
        pipeline_dict,
        job_data,
        callbacks=components.LeftPane.Callbacks(
            refresh=callback,
            refresh_data=get_job_data_fn,
            callback_manager=background_callback_manager,
        ),
    )

    layout_graph, fig = components.graph_col.generate(app, graph)

    def layout_container() -> dbc.Container:
        return dbc.Container(
            [
                html.Link(id="link-stylesheet", rel="stylesheet", href=dbc.themes.DARKLY),
                html.Link(id="link-tabulator-stylesheet", rel="stylesheet", href="/assets/tabulator_midnight.min.css"),
                dbc.Row(
                    [
                        left_pane,
                        layout_graph,
                    ],
                    class_name="g-2",
                ),
                dbc.Row(
                    [],
                    id="row-job-pane",
                    class_name="g-2",
                ),
                html.Div(id="hidden-div", hidden=True),
                dcc.Store(id=Ids.stores.figure_root),
                dcc.Store(id=Ids.stores.job_pane_data),
                dcc.Interval(id="intvl-job-pane-diagram-click", disabled=True, max_intervals=1, interval=200),
            ],
            fluid=True,
            id="dbc",
            className="dbc",
        )

    app.layout = layout_container()

    @app.callback(
        *components.GraphTooltip.callbacks.display.outputs,
        Input("pipeline-graph", "clickData"),
        *components.GraphTooltip.callbacks.display.inputs,
        prevent_initial_call=True,
    )
    def cb_pipeline_graph_click(click_data, *args, **kwargs) -> tuple:
        # pprint(click_data)
        points: list[dict] = click_data.get("points", [])
        if not points:
            raise PreventUpdate()
        customdata: network_graph.NodeCustomData = points[0].get("customdata", {})
        data = components.GraphTooltip.Data(
            name=customdata.get("name", "NO NAME"),
            serial=customdata.get("serial"),
            status=customdata.get("status", "Unknown"),
            url=customdata.get("url"),
            uuid=customdata.get("uuid", "UNKNOWN"),
        )
        bbox = points[0]["bbox"]

        return (*components.GraphTooltip.callbacks.display.function(bbox, data, *args, **kwargs),)

    @app.callback(
        Output(Ids.stores.job_pane_data, "data"),
        Input("el-info-click", "event"),
        prevent_initial_call=True,
    )
    def cb_input_job_info_click(e: dict):
        uuid = e.get("detail")
        if uuid is None:
            raise PreventUpdate
        sub_dict = find_pipeline(pipeline_dict, lambda _, p: p.get("uuid", "") == uuid)
        if sub_dict is None:
            raise PreventUpdate()
        job_name = sub_dict["name"]
        job_data_ = job_data.get(job_name, JobData.UNDEFINED)
        data = JobPane.Data(
            name=job_name,
            serial=job_data_.serial,
            status=job_data_.status.value,
            url=job_data_.url,
            uuid=sub_dict["uuid"],
        )
        return asdict(data)

    @app.callback(
        Output("row-job-pane", "children"),
        Input(Ids.stores.job_pane_data, "data"),
        prevent_initial_call=True,
    )
    def cb_store_job_pane_data_updated(data):
        data = JobPane.Data(**data)
        return [JobPane(app, data)]

    @app.callback(
        Output("pipeline-graph", "figure"),
        Input("pipeline-graph", "relayoutData"),
        State("pipeline-graph", "figure"),
        prevent_initial_call=True,
    )
    def graph_relayout(data, figure):
        if not data:
            raise PreventUpdate
        delta = data.get("yaxis.range[1]", 0) - data.get("yaxis.range[0]", 0)
        if not delta:
            if "autosize" in data or "yaxis.autorange" in data:
                delta = None
            else:
                raise PreventUpdate

        components.jobs_pipeline_fig.resize_fig_data_from_y_delta(figure, delta)
        return figure

    def setup_click_btn_left_pane_expand():
        this_toggle = False

        @app.callback(
            Output("col-left-pane", "style"),
            de.Trigger("btn-left-pane-expand", "n_clicks"),
            prevent_initial_call=True,
        )
        def click_btn_left_pane_expand():
            nonlocal this_toggle
            this_toggle = not this_toggle
            width = "100vw" if this_toggle else None
            return dict(width=width)

    setup_click_btn_left_pane_expand()

    @app.callback(
        Output(Ids.stores.figure_root, "data"),
        Input("el-diagram-click", "event"),
        Input("btn-diagram-root", "n_clicks"),
        prevent_initial_call=True,
    )
    def input_btn_diagram(e: dict, n_clicks):
        uuid: Optional[str]
        if dash.ctx.triggered_id == "btn-diagram-root":
            uuid = pipeline_dict["uuid"]
        else:
            uuid = e.get("detail")
        if uuid is None:
            raise PreventUpdate
        print(f"Callback: Btn Diagram {uuid}")
        return uuid

    @app.callback(
        Output("pipeline-graph", "figure"),
        Input(Ids.stores.figure_root, "data"),
        background=True,
        manager=background_callback_manager,
        prevent_initial_call=True,
    )
    def handle_new_figure_root(figure_root):
        start_time = time.process_time()
        sub_dict = find_pipeline(pipeline_dict, lambda _, p: p.get("uuid", "") == figure_root)
        nonlocal fig
        if sub_dict is None:
            raise PreventUpdate
        graph = generate_nx(sub_dict, job_data)
        end_time = time.process_time()
        print(f"Generated network in {end_time - start_time} sec")
        fig = components.jobs_pipeline_fig.generate_plot_figure(graph)
        return fig

    @app.callback(
        [
            Output("pipeline-graph", "figure"),
            Output("pipeline-graph", "responsive"),
        ],
        Input("cb-responsive-graph", "value"),
        State("pipeline-graph", "figure"),
        prevent_initial_call=True,
    )
    def btn_responsive_graph(responsive, figure):
        if not responsive:
            components.jobs_pipeline_fig.resize_fig_data_from_scale(figure, 0.8)
        else:
            components.jobs_pipeline_fig.resize_fig_data_from_y_delta(figure, None)
        return figure, responsive

    @app.callback(
        Output("link-stylesheet", "href"),
        Output("link-tabulator-stylesheet", "href"),
        Output("pipeline-graph", "figure"),
        Input("cb-dark-mode", "value"),
        State("pipeline-graph", "figure"),
    )
    def cb_dark_mode(dark, figure):
        if dark:
            # with (files("dash_bootstrap_templates") / "templates" / "darkly.json").open() as f:
            #     template = json.load(f)
            template = json.loads(files(__package__).joinpath("templates/darkly.json").read_text())
            plotly.io.templates["darkly"] = template
            plotly.io.templates.default = "darkly"
            figure["layout"]["template"] = template
            return dbc.themes.DARKLY, "/assets/tabulator_midnight.min.css", figure

        template = json.loads(files(__package__).joinpath("templates/bootstrap.json").read_text())
        plotly.io.templates["bootstrap"] = template
        plotly.io.templates.default = "bootstrap"
        figure["layout"]["template"] = template
        return dbc.themes.BOOTSTRAP, "/assets/tabulator_simple.min.css", figure

    app.run_server(debug=config.debug)
    # app.run(
    #     dev_tools_hot_reload=True,
    # )