-- Optional pre-deployment migration for ongoing period logs.
-- The existing forecasting schema setup also applies this change.
BEGIN;
ALTER TABLE IF EXISTS menstrual_cycle_history
    ALTER COLUMN period_end_date DROP NOT NULL;
COMMIT;
