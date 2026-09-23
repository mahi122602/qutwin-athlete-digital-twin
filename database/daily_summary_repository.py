"""Store observed daily summaries separately from predicted Digital Twin states."""
import json
import pandas as pd
from database.connection import get_connection
from ingestion.daily_summary import summary_records
from utils.performance import invalidate_reads, request_cached

SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS qutwin_daily_uploads (
 athlete_id TEXT NOT NULL, content_hash TEXT NOT NULL, filename TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (athlete_id, content_hash)
);
CREATE TABLE IF NOT EXISTS qutwin_daily_summaries (
 athlete_id TEXT NOT NULL, source TEXT NOT NULL, record_key TEXT NOT NULL,
 activity_date DATE NOT NULL, measurements JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (athlete_id, source, record_key)
);
ALTER TABLE qutwin_daily_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE qutwin_daily_summaries ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS qutwin_daily_summary_dates
 ON qutwin_daily_summaries (athlete_id, activity_date);
'''


@invalidate_reads
def save_daily_summary(athlete_id, filename, frame, content_hash):
    records = summary_records(frame)
    if not records:
        raise ValueError('No daily summary records to save.')
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            cur.execute('''INSERT INTO qutwin_daily_uploads
                (athlete_id, content_hash, filename) VALUES (%s,%s,%s)
                ON CONFLICT DO NOTHING RETURNING content_hash''',
                (str(athlete_id), content_hash, filename))
            if cur.fetchone() is None:
                conn.commit()
                return {'status': 'already_saved', 'inserted': 0, 'duplicates': len(records)}
            inserted = 0
            for key, activity_date, payload in records:
                cur.execute('''INSERT INTO qutwin_daily_summaries
                    (athlete_id, source, record_key, activity_date, measurements)
                    VALUES (%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT DO NOTHING RETURNING record_key''',
                    (str(athlete_id), 'Samsung Health', key, activity_date,
                     json.dumps(payload, allow_nan=False)))
                inserted += cur.fetchone() is not None
        conn.commit()
        return {'status': 'saved', 'inserted': inserted, 'duplicates': len(records)-inserted}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@request_cached
def get_daily_summaries(athlete_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('qutwin_daily_summaries')")
            if cur.fetchone()[0] is None:
                return pd.DataFrame()
            cur.execute('''SELECT activity_date, measurements FROM qutwin_daily_summaries
                WHERE athlete_id=%s ORDER BY activity_date, record_key''', (str(athlete_id),))
            rows = cur.fetchall()
        records = []
        for day, measurements in rows:
            data = json.loads(measurements) if isinstance(measurements,str) else dict(measurements)
            data['Date'] = day
            records.append(data)
        return pd.DataFrame(records)
    finally:
        conn.close()
