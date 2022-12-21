import functools

from line_profiler import line_profiler, LineProfiler  # type: ignore
from line_profiler_pycharm._profile import PyCharmLineProfiler  # type: ignore


def pcprofile(func):
    """Decorator for pycharm line_profiler"""

    @functools.wraps(func)
    def wrapper_profile(*args, **kwargs):
        lppc = PyCharmLineProfiler.get_instance()
        lp = LineProfiler()
        rv = lppc(func)(*args, **kwargs)
        lppc._dump_stats_for_pycharm(output_unit=1e-3)
        stats = lppc.get_stats()
        fn_timings = {k: v for k, v in stats.timings.items() if k[2] == func.__name__}
        line_profiler.show_text(fn_timings, stats.unit, output_unit=1e-3)

        return rv

    return wrapper_profile
