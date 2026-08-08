-- QUTwin gender-aware forecasting migration
-- Run this once against the same PostgreSQL database used by the application.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'athletes'
    ) THEN
        ALTER TABLE athletes
            ADD COLUMN IF NOT EXISTS gender VARCHAR(30);
        ALTER TABLE athletes
            ADD COLUMN IF NOT EXISTS menstrual_tracking_enabled BOOLEAN
            NOT NULL DEFAULT FALSE;
    ELSIF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'athlete_profile'
    ) THEN
        ALTER TABLE athlete_profile
            ADD COLUMN IF NOT EXISTS gender VARCHAR(30);
        ALTER TABLE athlete_profile
            ADD COLUMN IF NOT EXISTS menstrual_tracking_enabled BOOLEAN
            NOT NULL DEFAULT FALSE;
    ELSIF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'athlete_profiles'
    ) THEN
        ALTER TABLE athlete_profiles
            ADD COLUMN IF NOT EXISTS gender VARCHAR(30);
        ALTER TABLE athlete_profiles
            ADD COLUMN IF NOT EXISTS menstrual_tracking_enabled BOOLEAN
            NOT NULL DEFAULT FALSE;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS menstrual_cycle_history (
    cycle_id BIGSERIAL PRIMARY KEY,
    athlete_id VARCHAR(100) NOT NULL,
    period_start_date DATE NOT NULL,
    period_end_date DATE NOT NULL,
    symptoms TEXT,
    athlete_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_period_dates
        CHECK (period_end_date >= period_start_date),
    CONSTRAINT reasonable_period_duration
        CHECK ((period_end_date - period_start_date) BETWEEN 0 AND 14),
    CONSTRAINT unique_athlete_period_start
        UNIQUE (athlete_id, period_start_date)
);

CREATE INDEX IF NOT EXISTS idx_menstrual_history_athlete_date
ON menstrual_cycle_history (athlete_id, period_start_date DESC);

CREATE TABLE IF NOT EXISTS athlete_forecast_runs (
    forecast_run_id BIGSERIAL PRIMARY KEY,
    athlete_id VARCHAR(100) NOT NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    horizon_days INTEGER NOT NULL DEFAULT 7,
    gender_path VARCHAR(30) NOT NULL,
    validation_score NUMERIC(8,3),
    forecast_payload JSONB NOT NULL,
    evaluation_payload JSONB
);

CREATE INDEX IF NOT EXISTS idx_forecast_runs_athlete_time
ON athlete_forecast_runs (athlete_id, generated_at DESC);
