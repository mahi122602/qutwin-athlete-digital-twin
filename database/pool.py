"""Bounded, thread-safe connection reuse; repository close() releases a lease."""
from functools import lru_cache
from threading import BoundedSemaphore, Lock
from time import monotonic, perf_counter
import os
import weakref

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from utils.performance import _log


class _Lease:
    def __init__(self, owner, raw):
        self._raw = raw
        self._release = weakref.finalize(self, owner.release, raw)

    @property
    def closed(self):
        return not self._release.alive or self._raw.closed

    def __getattr__(self, name):
        if self.closed:
            raise psycopg2.InterfaceError('Connection lease is closed')
        return getattr(self._raw, name)

    def close(self):
        self._release()

    def __enter__(self):
        self._raw.__enter__()
        return self

    def __exit__(self, *args):
        # Match psycopg2: a transaction context commits/rolls back; it does
        # not close the connection. Existing explicit close() is supported.
        return self._raw.__exit__(*args)


class _Pool:
    def __init__(self, args, kwargs):
        self._pool = ThreadedConnectionPool(1, 6, *args, **kwargs)
        self._slots = BoundedSemaphore(6)
        self._last_return = {}
        self._lock = Lock()

    def acquire(self):
        if not self._slots.acquire(timeout=15):
            raise psycopg2.OperationalError('Database is busy; please retry shortly')
        raw = None
        try:
            raw = self._pool.getconn()
            with self._lock:
                returned = self._last_return.pop(id(raw), None)
            if raw.closed:
                self._pool.putconn(raw, close=True)
                raw = None
                raw = self._pool.getconn()
            elif returned is not None and monotonic() - returned > 60:
                # Check idle sockets before handing them out. Never replay
                # an application query or write after a connection error.
                try:
                    with raw.cursor() as cursor:
                        cursor.execute('SELECT 1')
                    raw.rollback()
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    self._pool.putconn(raw, close=True)
                    raw = None
                    raw = self._pool.getconn()
            return _Lease(self, raw)
        except BaseException:
            if raw is not None:
                self._pool.putconn(raw, close=True)
            self._slots.release()
            raise

    def release(self, raw):
        try:
            # putconn rolls back open/failed transactions before reuse.
            # Repositories keep their existing explicit commit semantics.
            self._pool.putconn(raw)
            if not raw.closed:
                with self._lock:
                    self._last_return[id(raw)] = monotonic()
        except Exception:
            # A broken rollback must not leave the connection registered
            # as borrowed in the underlying pool.
            try:
                self._pool.putconn(raw, close=True)
            finally:
                raw.close()
        finally:
            self._slots.release()


_pool_lock = Lock()


@lru_cache(maxsize=4)
def _get_pool(args, kwargs):
    return _Pool(args, dict(kwargs))


def connect(*args, **kwargs):
    if os.getenv('QUTWIN_DB_POOL', '1') == '0':
        return psycopg2.connect(*args, **kwargs)
    started = perf_counter()
    try:
        # Config (including URL/SSL options) remains exactly as supplied.
        # Serialize creation to prevent duplicate pools on first login.
        with _pool_lock:
            pool = _get_pool(args, tuple(sorted(kwargs.items())))
        return pool.acquire()
    finally:
        _log('database_connection_acquire', started)
