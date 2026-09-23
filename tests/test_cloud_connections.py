import gc
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database.pool import _Pool
import psycopg2


class PoolTests(unittest.TestCase):
    def make_pool(self):
        raw = MagicMock()
        raw.closed = False
        factory = MagicMock()
        factory.return_value.getconn.return_value = raw
        with patch('database.pool.ThreadedConnectionPool', factory):
            pool = _Pool((), {})
        return pool, raw, factory.return_value

    def test_close_returns_connection_once(self):
        pool, raw, backend = self.make_pool()
        lease = pool.acquire()
        self.assertIs(lease.cursor(), raw.cursor.return_value)
        lease.commit()
        raw.commit.assert_called_once()
        lease.close()
        lease.close()
        backend.putconn.assert_called_once_with(raw)
        self.assertTrue(lease.closed)
        with self.assertRaises(psycopg2.InterfaceError):
            lease.cursor()
        self.assertIs(pool.acquire()._raw, raw)

    def test_abandoned_lease_is_returned(self):
        pool, raw, backend = self.make_pool()
        lease = pool.acquire()
        del lease
        gc.collect()
        backend.putconn.assert_called_once_with(raw)

    def test_stale_socket_replaced_before_query(self):
        pool, raw, backend = self.make_pool()
        pool._last_return[id(raw)] = -1000
        raw.cursor.side_effect = psycopg2.OperationalError('disconnected')
        fresh = MagicMock(closed=False)
        backend.getconn.side_effect = [raw, fresh]
        lease = pool.acquire()
        self.assertIs(lease._raw, fresh)
        backend.putconn.assert_called_once_with(raw, close=True)
        lease.close()

    def test_failed_acquire_releases_capacity(self):
        pool, raw, backend = self.make_pool()
        backend.getconn.side_effect = psycopg2.OperationalError('offline')
        for _ in range(8):
            with self.assertRaisesRegex(psycopg2.OperationalError, 'offline'):
                pool.acquire()

    def test_broken_release_discards_connection(self):
        pool, raw, backend = self.make_pool()
        backend.putconn.side_effect = [psycopg2.OperationalError('lost'), None]
        lease = pool.acquire()
        lease.close()
        self.assertEqual(backend.putconn.call_count, 2)
        backend.putconn.assert_called_with(raw, close=True)

    def test_transaction_context_delegates(self):
        pool, raw, backend = self.make_pool()
        raw.__exit__.return_value = False
        lease = pool.acquire()
        with self.assertRaises(ValueError):
            with lease:
                raise ValueError('cancel transaction')
        self.assertEqual(raw.__exit__.call_args.args[0], ValueError)
        lease.close()
