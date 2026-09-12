"""Reuse inference artifacts; reload when the underlying file changes."""
from functools import lru_cache
from pathlib import Path
import joblib


@lru_cache(maxsize=16)
def _load(path, modified_ns, size):
    return joblib.load(path)


def load_model(path):
    resolved = Path(path).resolve()
    stat = resolved.stat()
    return _load(str(resolved), stat.st_mtime_ns, stat.st_size)
