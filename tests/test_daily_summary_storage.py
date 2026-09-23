import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import pandas as pd
from ingestion.daily_summary import prepare_daily_summary
from database.daily_summary_repository import save_daily_summary, get_daily_summaries
from utils.performance import begin_run

class Cursor:
    def __init__(self, conn): self.cur=conn.cursor(); self.override=None
    def __enter__(self): return self
    def __exit__(self,*args): self.cur.close()
    def execute(self, sql, params=()):
        if 'to_regclass' in sql:
            self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='qutwin_daily_summaries'")
            self.override=self.cur.fetchone() or (None,)
            return
        statements=[s.strip() for s in sql.split(';') if s.strip()]
        for s in statements:
            if "ENABLE ROW LEVEL SECURITY" in s: continue  # PostgreSQL-specific; not simulated
            self.cur.execute(s.replace('%s','?').replace('::jsonb',''), params)
    def fetchone(self):
        if self.override is not None:
            r=self.override; self.override=None; return r
        return self.cur.fetchone()
    def fetchall(self): return self.cur.fetchall()
class Connection:
    def __init__(self,path): self.conn=sqlite3.connect(path)
    def cursor(self): return Cursor(self.conn)
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self): self.conn.close()

class DailySummaryTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=str(Path(self.temp.name)/'test.db')
        self.mock=patch('database.daily_summary_repository.get_connection',side_effect=lambda:Connection(self.path));self.mock.start()
        begin_run()
        self.frame=pd.DataFrame({'day_time':['2026-08-15','2026-08-16'],'step_count':[10,20],'datauuid':['a','b'],'sleep_hours':[None,None]})
    def tearDown(self): self.mock.stop(); self.temp.cleanup()
    def test_save_roundtrip_dates_and_missing_values(self):
        result=save_daily_summary('one','file.csv',self.frame,'hash')
        self.assertEqual(result['inserted'],2)
        data=get_daily_summaries('one')
        self.assertEqual(data['Date'].tolist(),['2026-08-15','2026-08-16'])
        self.assertEqual(data.step_count.tolist(),[10,20])
        self.assertTrue(data.sleep_hours.isna().all())
        self.assertNotIn('fatigue_score',data)
    def test_duplicate_file_and_overlapping_export(self):
        save_daily_summary('one','file.csv',self.frame,'hash')
        self.assertEqual(save_daily_summary('one','file.csv',self.frame,'hash')['status'],'already_saved')
        self.assertEqual(save_daily_summary('one','other.csv',self.frame,'different')['inserted'],0)
        self.assertEqual(len(get_daily_summaries('one')),2)
    def test_athlete_isolation(self):
        save_daily_summary('one','file.csv',self.frame,'hash')
        self.assertTrue(get_daily_summaries('two').empty)
        self.assertEqual(save_daily_summary('two','file.csv',self.frame,'hash')['inserted'],2)
    def test_invalid_date_has_no_partial_write(self):
        self.frame.loc[1,'day_time']='bad date'
        with self.assertRaises(ValueError): save_daily_summary('one','file.csv',self.frame,'hash')
        self.assertTrue(get_daily_summaries('one').empty)
    def test_failure_rolls_back_records_and_upload_marker(self):
        save_daily_summary('one','initial.csv',self.frame.iloc[:1],'initial')
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TRIGGER fail_second BEFORE INSERT ON qutwin_daily_summaries WHEN NEW.record_key='b' BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(sqlite3.IntegrityError): save_daily_summary('one','file.csv',self.frame,'hash')
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM qutwin_daily_uploads WHERE content_hash='hash'").fetchone()[0],0)
        self.assertEqual(len(get_daily_summaries('one')),1)
