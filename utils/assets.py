"""Cache asset conversion until a file changes on disk."""
from functools import lru_cache, wraps
from pathlib import Path


def cache_file_result(function):
    @lru_cache(maxsize=8)
    def cached(path, modified_ns, size):
        return function(Path(path))

    @wraps(function)
    def wrapped(path):
        try:
            resolved = Path(path).resolve()
            stat = resolved.stat()
        except OSError:
            return function(path)
        return cached(str(resolved), stat.st_mtime_ns, stat.st_size)
    return wrapped
