-- Run once in the Supabase SQL editor before deploying this update.
BEGIN;
CREATE TABLE IF NOT EXISTS notifications (
 notification_id SERIAL PRIMARY KEY, request_id INTEGER,
 recipient_role TEXT NOT NULL, recipient_id TEXT NOT NULL,
 notification_type TEXT NOT NULL, message TEXT NOT NULL,
 is_read BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE notifications ALTER COLUMN request_id DROP NOT NULL;
CREATE TABLE IF NOT EXISTS qutwin_processed_uploads (
 id BIGSERIAL PRIMARY KEY, athlete_id TEXT NOT NULL,
 content_hash TEXT NOT NULL, filename TEXT NOT NULL, source TEXT NOT NULL,
 uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 legacy_upload_id INTEGER, records JSONB NOT NULL, snapshot JSONB NOT NULL,
 events JSONB NOT NULL, assignments JSONB NOT NULL,
 processing_status TEXT NOT NULL,
 ai_status TEXT NOT NULL DEFAULT 'pending', ai_text TEXT, ai_model TEXT,
 ai_error TEXT, ai_started_at TIMESTAMPTZ, ai_token TEXT,
 UNIQUE(athlete_id, content_hash)
);
CREATE INDEX IF NOT EXISTS qutwin_processed_uploads_latest
 ON qutwin_processed_uploads(athlete_id, uploaded_at DESC, id DESC);
CREATE TABLE IF NOT EXISTS qutwin_recommendation_reviews (
 id BIGSERIAL PRIMARY KEY, upload_id BIGINT NOT NULL REFERENCES qutwin_processed_uploads(id),
 coach_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending'
 CHECK(status IN ('Pending','Approved','Rejected','Modified')),
 comment TEXT, final_text TEXT, reviewed_at TIMESTAMPTZ,
 UNIQUE(upload_id,coach_id)
);
ALTER TABLE qutwin_processed_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE qutwin_recommendation_reviews ENABLE ROW LEVEL SECURITY;
-- Direct server-side PostgreSQL connection is used; no anonymous policies.
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS event_type TEXT;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS acwr DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS recovery_index DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS environmental_stress DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS fatigue_index DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS readiness_index DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS twin_score DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS health_index DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS state_explanation TEXT;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS heart_rate_trend DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS sleep_trend DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS training_load_trend DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS readiness_trend DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS fatigue_trend DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS trend_summary TEXT;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS bayesian_fatigue_probability DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS prediction_confidence DOUBLE PRECISION;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS digital_twin_state TEXT;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS user_status_message TEXT;
ALTER TABLE digital_athlete_state ADD COLUMN IF NOT EXISTS upload_id INTEGER;
COMMIT;
