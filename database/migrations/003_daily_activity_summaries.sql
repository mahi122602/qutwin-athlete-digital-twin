
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
