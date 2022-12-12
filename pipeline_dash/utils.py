import time
from functools import wraps


def timeit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.process_time()
        ret = f(*args, **kwargs)
        end_time = time.process_time()
        print(f"{getattr(f, '__name__', None)} executed in {end_time - start_time} sec")
        return ret

    return wrapper


def next_get(iterable, default):
    """Like next(iterable), but will return default if no next item in iterable"""
    try:
        return next(iterable)
    except StopIteration:
        return default
