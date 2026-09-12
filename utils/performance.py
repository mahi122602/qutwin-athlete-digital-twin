"""Per-run read reuse and opt-in timings without logging personal data."""
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import json
import os
import sys
from time import perf_counter

_reads = ContextVar('qutwin_run_reads', default=None)


def begin_run():
    # Streamlit executes app.py on every interaction. No cross-run/user cache.
    _reads.set({})


def clear_reads():
    cache = _reads.get()
    if cache is not None:
        cache.clear()


def _log(name, started, cache_hit=False):
    if os.getenv('QUTWIN_PROFILE', '').lower() in ('1', 'true', 'yes'):
        print(json.dumps({'operation': name, 'elapsed_ms': round((perf_counter()-started)*1000, 3),
                          'cache_hit': cache_hit}), file=sys.stderr)


def request_cached(function):
    """Reuse identical reads only inside the current script execution.

    Copies prevent callers mutating another page component's data. Without
    begin_run (e.g. CLI scripts), calls always execute normally.
    """
    @wraps(function)
    def wrapped(*args, **kwargs):
        started = perf_counter()
        cache = _reads.get()
        key = (function.__module__, function.__qualname__, args, tuple(sorted(kwargs.items())))
        try:
            hash(key)
        except TypeError:
            cache = None
        if cache is not None and key in cache:
            _log(function.__qualname__, started, True)
            return deepcopy(cache[key])
        try:
            result = function(*args, **kwargs)
            if cache is not None:
                try:
                    cache[key] = deepcopy(result)
                except TypeError:
                    # PostgreSQL BYTEA can return memoryview (e.g. photos).
                    # Preserve the original result and bypass optional caching
                    # when a value cannot be copied safely.
                    pass
            return result
        finally:
            _log(function.__qualname__, started)
    return wrapped


def invalidate_reads(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        clear_reads()
        started = perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            clear_reads()
            _log(function.__qualname__, started)
    return wrapped
