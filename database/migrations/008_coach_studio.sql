-- Apply once in Supabase SQL Editor using the project database owner.
-- Additive migration: existing athlete, upload and review data is preserved.
BEGIN;
CREATE TABLE IF NOT EXISTS qutwin_coach_profiles (
 coach_id VARCHAR(50) PRIMARY KEY REFERENCES coaches(coach_id) ON DELETE CASCADE,
 email TEXT NOT NULL DEFAULT '', organisation TEXT NOT NULL DEFAULT '',
 specialties TEXT NOT NULL DEFAULT '', updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS qutwin_coach_teams (
 id BIGSERIAL PRIMARY KEY, coach_id VARCHAR(50) NOT NULL REFERENCES coaches(coach_id) ON DELETE CASCADE,
 name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 100), description TEXT NOT NULL DEFAULT '',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(coach_id,name), UNIQUE(id,coach_id)
);
CREATE TABLE IF NOT EXISTS qutwin_team_members (
 team_id BIGINT NOT NULL, coach_id VARCHAR(50) NOT NULL, athlete_id VARCHAR(50) NOT NULL,
 PRIMARY KEY(team_id,athlete_id),
 FOREIGN KEY(team_id,coach_id) REFERENCES qutwin_coach_teams(id,coach_id) ON DELETE CASCADE,
 FOREIGN KEY(coach_id,athlete_id) REFERENCES coach_athlete_mapping(coach_id,athlete_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS qutwin_team_members_coach ON qutwin_team_members(coach_id,athlete_id);
ALTER TABLE qutwin_coach_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE qutwin_coach_teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE qutwin_team_members ENABLE ROW LEVEL SECURITY;
-- No anonymous/client API policies. Existing server-side PostgreSQL access is used.
DO $$ BEGIN
 IF to_regclass('public.coach_recommendations') IS NOT NULL THEN
  ALTER TABLE public.coach_recommendations ALTER COLUMN coach_id DROP NOT NULL;
 END IF;
END $$;
COMMIT;
