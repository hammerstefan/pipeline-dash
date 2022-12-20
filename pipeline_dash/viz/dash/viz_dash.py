import json
import time
from dataclasses import asdict, dataclass
from importlib.resources import files
from typing import Callable, Optional

import dash  # type: ignore
import dash_bootstrap_components as dbc  # type: ignore
import dash_bootstrap_templates  # type: ignore
import diskcache  # type: ignore
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
from .logged_callback import logged_callback
from .network_graph import generate_nx
from .partial_callback import PartialCallback


class Ids:
    class StoreIds:
        figure_root = "store-figure-root"
        job_pane_data = "store-job-pane-date"
        job_config_name = "store-job-config-name"

    stores = StoreIds


@dataclass
class Config:
    job_configs: list[str]
    debug: bool = False


def display_dash(get_job_data_fn: Callable[[str], tuple[PipelineDict, JobDataDict]], config: Config):

    cache = diskcache.Cache("./.diskcache/dash")  # type: ignore
    background_callback_manager = dash.DiskcacheManager(cache)
    pipeline_dict, job_data = get_job_data_fn(config.job_configs[0])
    cache["pipeline_dict"] = pipeline_dict
    cache["job_data"] = job_data
    graph = generate_nx(pipeline_dict, job_data)
    app = de.DashProxy(
        __name__,
        external_stylesheets=[
            dbc.icons.BOOTSTRAP,
        ],
        transforms=[
            de.TriggerTransform(),
            de.MultiplexerTransform(),
            de.NoOutputTransform(),
            # de.OperatorTransform(),
        ],
        assets_ignore="tabulator_.*css",
        background_callback_manager=background_callback_manager,
        # suppress_callback_exceptions=True,
    )
    dash_bootstrap_templates.load_figure_template("darkly")

    @logged_callback
    def callback_refresh(job_config_name, figure_root) -> tuple[go.Figure, list[dict], str]:
        _pipeline_dict = cache["pipeline_dict"]
        # TODO: don't regen the world just to refresh some data from Jenkins
        print(f"CALLBACK {job_config_name} {figure_root}")
        pipeline_dict_new, job_data_new = get_job_data_fn(job_config_name)
        if rv := translate_uuid(figure_root, _pipeline_dict, pipeline_dict_new):
            figure_root, sub_dict = rv
            print(f"Sub dict found: True")
        else:
            sub_dict = pipeline_dict_new
            print(f"Sub dict found: False")
        graph_ = generate_nx(sub_dict, job_data_new)
        fig_ = components.jobs_pipeline_fig.generate_plot_figure(graph_)
        table_data = components.LeftPane.generate_job_details(pipeline_dict_new, job_data_new)
        cache["pipeline_dict"] = pipeline_dict_new
        cache["job_data"] = job_data_new
        return fig_, table_data, figure_root

    callback: components.LeftPane.Callbacks.RefreshCallbackType = PartialCallback(
        outputs=[
            Output("pipeline-graph", "figure"),
            Output("jobs_table", "data"),
            Output(Ids.stores.figure_root, "data"),
        ],
        inputs=[
            State(components.LeftPane.ids.selects.job_config, "value"),
            State(Ids.stores.figure_root, "data"),
        ],
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
        config=components.LeftPane.Config(job_configs=config.job_configs),
    )

    layout_graph, fig = components.graph_col.generate(app, graph)

    def layout_container() -> list:
        return [
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
        ]

    app.layout = html.Div(
        [
            dcc.Store(id=Ids.stores.job_config_name, data=config.job_configs[0]),
            dbc.Container(
                layout_container(),
                fluid=True,
                id="dbc",
                className="dbc",
            ),
        ],
    )

    @app.callback(
        *components.GraphTooltip.callbacks.display.outputs,
        Input("pipeline-graph", "clickData"),
        *components.GraphTooltip.callbacks.display.inputs,
        prevent_initial_call=True,
    )
    @logged_callback
    def cb_pipeline_graph_click(click_data, *args, **kwargs) -> tuple:
        if click_data is None:
            raise PreventUpdate()
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
    @logged_callback
    def cb_input_job_info_click(e: dict):
        if e is None:
            raise PreventUpdate()
        uuid = e.get("detail")
        if uuid is None:
            raise PreventUpdate
        _pipeline_dict = cache["pipeline_dict"]
        sub_dict = find_pipeline(_pipeline_dict, lambda _, p: p.get("uuid", "") == uuid)
        if sub_dict is None:
            raise PreventUpdate()
        job_name = sub_dict["name"]
        job_data_ = job_data.get(job_name, JobData.UNDEFINED)
        data = JobPane.Data(
            name=job_name,
            serial=job_data_.serial,
            status=job_data_.status.value,
            url=job_data_.human_url,
            uuid=sub_dict["uuid"],
        )
        return asdict(data)

    @app.callback(
        Output("row-job-pane", "children"),
        Input(Ids.stores.job_pane_data, "data"),
        prevent_initial_call=True,
    )
    @logged_callback
    def cb_store_job_pane_data_updated(data):
        if data is None:
            raise PreventUpdate()
        data = JobPane.Data(**data)
        return [JobPane(app, data)]

    @app.callback(
        Output("pipeline-graph", "figure"),
        Input("pipeline-graph", "relayoutData"),
        State("pipeline-graph", "figure"),
        prevent_initial_call=True,
    )
    @logged_callback
    def cb_graph_relayout(data, figure):
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

    def setup_cb_btn_left_pane_expand_click():
        this_toggle = False

        @app.callback(
            Output("col-left-pane", "style"),
            de.Trigger("btn-left-pane-expand", "n_clicks"),
            prevent_initial_call=True,
        )
        @logged_callback
        def cb_btn_left_pane_expand_click():
            nonlocal this_toggle
            this_toggle = not this_toggle
            width = "100vw" if this_toggle else None
            return dict(width=width)

    setup_cb_btn_left_pane_expand_click()

    @app.callback(
        Output(Ids.stores.figure_root, "data"),
        Input("el-diagram-click", "event"),
        Input(components.LeftPane.ids.buttons.diagram_root, "n_clicks"),
        prevent_initial_call=True,
    )
    @logged_callback
    def cb_btn_diagram_click(e: dict, n_clicks):
        if e is None and n_clicks is None:
            raise PreventUpdate()
        uuid: Optional[str]
        if dash.ctx.triggered_id == components.LeftPane.ids.buttons.diagram_root:
            _pipeline_dict = cache["pipeline_dict"]
            uuid = _pipeline_dict["uuid"]
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
        prevent_initial_call=True,
    )
    @logged_callback
    def cb_handle_new_figure_root(figure_root):
        if figure_root is None:
            raise PreventUpdate()
        start_time = time.process_time()
        _pipeline_dict = cache["pipeline_dict"]
        sub_dict = find_pipeline(_pipeline_dict, lambda _, p: p.get("uuid", "") == figure_root)
        nonlocal fig
        if sub_dict is None:
            print(f"Callback(cb_handle_new_figure_root): sub_dict for {figure_root} not found")
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
        Input(components.LeftPane.ids.checkboxes.responsive_graph, "value"),
        State("pipeline-graph", "figure"),
        prevent_initial_call=True,
    )
    @logged_callback
    def cb_btn_responsive_graph_toggle(responsive, figure):
        if responsive is None:
            raise PreventUpdate()
        if not responsive:
            components.jobs_pipeline_fig.resize_fig_data_from_scale(figure, 0.8)
        else:
            components.jobs_pipeline_fig.resize_fig_data_from_y_delta(figure, None)
        return figure, responsive

    @app.callback(
        Output("link-stylesheet", "href"),
        Output("link-tabulator-stylesheet", "href"),
        Output("pipeline-graph", "figure"),
        Input(components.LeftPane.ids.checkboxes.dark_mode, "value"),
        State("pipeline-graph", "figure"),
    )
    @logged_callback
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
