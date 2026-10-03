-- Optional remembered location. The server repository creates this automatically
-- when permitted. Run manually as database owner only if automatic setup fails.
CREATE TABLE IF NOT EXISTS qutwin_training_locations (
    athlete_id TEXT PRIMARY KEY,
    preferences JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE qutwin_training_locations ENABLE ROW LEVEL SECURITY;
-- Access is through the existing trusted server database connection.
-- No public/anonymous policies are created.
