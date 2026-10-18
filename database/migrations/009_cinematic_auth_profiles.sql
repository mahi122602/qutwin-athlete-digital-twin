-- Non-destructive. Existing athlete/coach credentials and IDs are retained.
-- Also run automatically inside the first successful signup transaction.
CREATE TABLE IF NOT EXISTS qutwin_auth_profiles (
    role TEXT NOT NULL CHECK (role IN ('Athlete', 'Coach')),
    user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role, user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS qutwin_auth_profiles_role_email
    ON qutwin_auth_profiles (role, lower(email));
