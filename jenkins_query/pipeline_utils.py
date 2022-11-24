from typing import Any, Callable, Union


def recurse_pipeline(pipeline: Union[dict, list], fn: Callable[[str, Union[dict, list], Any], Any], *args, **kwargs):
    rets = []
    if isinstance(pipeline, dict):
        for k, v in pipeline.items():
            if k.startswith("__") and k.endswith("__"):
                continue
            ret = fn(k, v, *args, **kwargs)
            if ret is not None:
                rets.append(ret)
    elif isinstance(pipeline, list):
        for k in pipeline:
            if type(k) is dict:
                _name = next(iter(k))
            else:
                _name = k
            if _name.startswith("__") and _name.endswith("__"):
                continue
            ret = fn(_name, [], *args, **kwargs)
            if ret is not None:
                rets.append(ret)
    return rets if rets else None


def find_pipeline(pipeline: dict, select_fn: Callable[[str, dict], bool]) -> dict:
    def _find(name_, pipeline_):
        if select_fn(name_, pipeline_):
            return {name_: pipeline_}
        rv = recurse_pipeline(pipeline_, _find)
        return rv[0] if rv is not None else None

    if select_fn("", pipeline):
        return pipeline
    return _find("", pipeline)
