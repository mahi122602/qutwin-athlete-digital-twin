import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.performance import begin_run, request_cached, invalidate_reads
from utils.assets import cache_file_result


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        begin_run()

    def test_read_reuse_and_independent_copies(self):
        calls = []
        @request_cached
        def read(user):
            calls.append(user)
            return {'items': [user]}
        a = read('athlete11')
        a['items'].append('changed')
        self.assertEqual(read('athlete11'), {'items':['athlete11']})
        self.assertEqual(len(calls), 1)
        read('athlete12')
        self.assertEqual(len(calls), 2)
        begin_run()
        read('athlete11')
        self.assertEqual(len(calls), 3)

    def test_memoryview_profile_bypasses_cache(self):
        calls = []
        @request_cached
        def read():
            calls.append(1)
            return {'profile_photo': memoryview(b'photo'), 'name': 'Athlete'}
        first = read()
        self.assertIsInstance(first['profile_photo'], memoryview)
        self.assertEqual(bytes(first['profile_photo']), b'photo')
        first['name'] = 'Changed'
        self.assertEqual(read()['name'], 'Athlete')
        self.assertEqual(len(calls), 2)

    def test_database_typeerror_is_not_suppressed(self):
        @request_cached
        def read():
            raise TypeError('query failed')
        with self.assertRaisesRegex(TypeError, 'query failed'):
            read()

    def test_writes_and_failed_writes_invalidate(self):
        calls = []
        @request_cached
        def read():
            calls.append(1)
            return len(calls)
        @invalidate_reads
        def write(fail=False):
            if fail:
                raise ValueError('failed')
        self.assertEqual(read(), 1)
        write()
        self.assertEqual(read(), 2)
        with self.assertRaises(ValueError):
            write(True)
        self.assertEqual(read(), 3)

    def test_thread_isolation(self):
        @request_cached
        def read(user):
            return {'user':user}
        def run(user):
            begin_run()
            return read(user)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, ['athlete11', 'athlete12']))
        self.assertEqual(results, [{'user':'athlete11'}, {'user':'athlete12'}])

    def test_asset_changes_reload(self):
        calls=[]
        @cache_file_result
        def read(path):
            calls.append(1)
            return path.read_text()
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'asset.txt'
            p.write_text('first')
            self.assertEqual(read(p), 'first')
            read(p)
            self.assertEqual(len(calls), 1)
            p.write_text('second version')
            self.assertEqual(read(p), 'second version')
            self.assertEqual(len(calls), 2)

    def test_models_reused_and_reloaded_on_change(self):
        from prediction.model_store import load_model, _load
        _load.cache_clear()
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'model.pkl'
            p.write_bytes(b'model')
            with patch('prediction.model_store.joblib.load', side_effect=lambda path: object()) as loader:
                first=load_model(p)
                self.assertIs(first, load_model(p))
                self.assertEqual(loader.call_count, 1)
                p.write_bytes(b'updated model')
                self.assertIsNot(first, load_model(p))
                self.assertEqual(loader.call_count, 2)

    def test_compatibility_modules_are_lazy(self):
        import subprocess
        root=str(Path(__file__).resolve().parents[1])
        program="import sys; import views.athlete_pages, views.coach_pages, views.auth_pages; assert 'streamlit' not in sys.modules; assert 'statsmodels' not in sys.modules; assert 'views.athlete.profile' not in sys.modules"
        subprocess.run([sys.executable, '-c', program], cwd=root, check=True)

if __name__ == '__main__':
    unittest.main()
