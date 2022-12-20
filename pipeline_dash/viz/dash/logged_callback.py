import functools
import inspect
import logging
import time
from pprint import pformat
from textwrap import TextWrapper
from typing import Callable

logger = logging.getLogger("pipeline_dash.callbacks")

_text_wrapper = TextWrapper(initial_indent="", subsequent_indent="    ", width=120)


def _indent(s: str):
    return "\n".join(_text_wrapper.wrap(s))


def logged_callback(func: Callable, level=logging.DEBUG, args_depth=2):
    module = inspect.getmodule(func)
    module_prefix = f"{module.__name__}." if module else ""
    full_func_name = f"{module_prefix}{func.__name__}"

    @functools.wraps(func)
    def wrapper_logging(*args, **kwargs):
        start_time = time.process_time()
        logger.log(
            level,
            f"Callback {full_func_name} called:"
            + ("\n" + "  Args:  " + _indent(pformat(args, compact=True, depth=args_depth)) if len(args) else "")
            + ("\n" + "  Kwargs:" + _indent(pformat(kwargs, compact=True, depth=args_depth)) if len(kwargs) else ""),
        )
        rv = func(*args, **kwargs)
        end_time = time.process_time()
        logger.log(level, f"Callback {full_func_name} completed in {end_time - start_time}s")
        return rv

    if logger.isEnabledFor(level):
        return wrapper_logging
    else:
        return func
