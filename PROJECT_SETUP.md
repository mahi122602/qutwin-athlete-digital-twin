# QUTwin: your existing project and database

This folder runs through `app.py`. Its Coach route calls
`views/coach/portal.py`, which opens the corrected Coach Studio. Athlete routes,
authentication, forecasting, recommendations and existing models remain in the
project. Run it from your usual Python environment:

```powershell
cd "C:\Users\mahib\OneDrive\Desktop\projects\athlete_digital_twin_github"
streamlit run app.py
```

The delivered installer updates that exact project folder after verifying the
incoming files. It backs up every application file it replaces beside the
project, preserves `.git`, `config.py`, `.streamlit`, `.env` files, environments
and uploads, and merges missing ignore rules. It does not connect to PostgreSQL
or push to GitHub. Old unreferenced files are left in place; run the root
`app.py` shown above.

## What the backend already saves

Teams and individual athletes use the same configured PostgreSQL database.
Team membership links existing athlete accounts; it does not create a separate
copy of an athlete's activity or health history. An athlete can be connected to
more than one coach and can belong to more than one team. A connected athlete
can also remain outside any team and still appear in the coach's Athletes page.

| Feature | Persistent tables | Existing behavior |
| --- | --- | --- |
| Athlete and coach accounts | `athletes`, `coaches` | Existing login and profile records |
| Coach profile details | `qutwin_coach_profiles` | Email, organisation and specialties |
| Connected individual athletes | `coach_athlete_mapping` | Coach/athlete relationship, independent of teams |
| Connection requests | `connection_requests` | Pending, accepted/rejected request records |
| Team name and description | `qutwin_coach_teams` | Team creation linked to its owning coach |
| Team membership | `qutwin_team_members` | Add/remove an already-connected athlete |
| Activity uploads and twin history | `uploaded_files`, `digital_athlete_state`, `qutwin_processed_uploads` | Existing upload metadata, processed records, event assignments and snapshots |
| AI drafts and review decisions | `qutwin_processed_uploads`, `qutwin_recommendation_reviews` | Draft, approval/rejection/edit, feedback and review timestamp |
| Notifications | `notifications` | Messages and read status |
| Daily summaries | `qutwin_daily_uploads`, `qutwin_daily_summaries` | Existing daily-summary workflow, when used |
| Saved forecast runs and private cycle history | `athlete_forecast_runs`, `menstrual_cycle_history` | Existing athlete forecasting workflow; privacy guards remain |

`database/coach_studio.py` commits team creation, member changes, coach profile
changes and disconnects to PostgreSQL. The UI reloads these records on each
visit. Team ownership is checked before changes. Membership also requires the
coach/athlete connection, enforced by a composite foreign key.

Removing an athlete from a team preserves the athlete's account and coach
connection. Disconnecting an athlete removes that coach's team memberships via
the connection foreign key, while keeping the athlete's account and uploads.
The current Teams UI supports creating a team, adding/removing members and
opening its detail page. Standalone team rename/delete controls and saved
team-wide training plans are additional features, not implemented by this UI
repair. Separate team-level prediction models are also not included.

Team attention counts, charts and dashboard totals are derived from saved
individual athlete records. They do not need a second table merely to retain
the same totals. Team priority counts are not a team injury probability.
Theme choice, navigation, search text and filters are session state and may
reset on a new session; this version does not save those UI preferences to the
database. Gemini settings are configuration, not athlete records.

## Database steps

Keep your current working connection. The connection priority is environment
`DATABASE_URL`, then complete environment `DB_*` fields, then top-level
Streamlit secrets with `DATABASE_URL` or complete `DB_*` fields, then local
`config.py` / `DB_CONFIG`. Neither changing the project directory nor pushing
to GitHub transfers an existing database.

From your actual project folder and normal Python environment:

```powershell
python -m utils.check_coach_database
```

This is a metadata/grant check in a read-only transaction. It reports required
tables/columns, CRUD privileges, insert sequence access and RLS restrictions.
It does not print credentials, inspect athlete records or create records. It
does not certify every optional athlete feature or execute real save actions.

The Coach repository already checks workflow migration `005` and Coach Studio
migration `008` before use, adding missing structures to the configured
existing database. If required, run explicitly:

```powershell
python -m utils.check_coach_database --setup
```

If your application role cannot perform setup, the database owner can execute
`database/migrations/005_upload_review_workflow.sql` followed by
`database/migrations/008_coach_studio.sql` against that SAME database in pgAdmin
or the Supabase SQL Editor, according to where it is hosted. Do not run a
migration in Supabase expecting it to update a separate local PostgreSQL
database. These steps do not bootstrap a new empty account database.

For the final live persistence check, create a test team using the Coach UI,
add a connected athlete, sign out, sign back in and reopen Teams. Restart the
Streamlit process and confirm again. Do not delete a real athlete account as a
test. The local installer and the default database checker do not perform this
live write test for you.

## GitHub and a hosted app

Continue using your existing repository and branch. The installer preserves
the existing `.git` directory and remote settings. No GitHub change has been
made by this delivery. First inspect the update:

```powershell
git status --short
git diff --stat
git branch --show-current
git ls-files -- config.py .streamlit/secrets.toml
```

The last command should list no private settings. `.gitignore` does not remove
files that Git already tracks. If that command lists a private file, remove
ONLY that listed file from tracking with `git rm --cached -- <listed-path>`;
this keeps the local file. Do not paste credentials into a commit or report.

Stage the application update explicitly, inspect it, then commit and push when
you are ready:

```powershell
git add -- app.py database ui views utils tests requirements.txt .gitignore README.md PROJECT_SETUP.md RUN_QUTWIN.bat CHECK_COACH_DATABASE.bat SETUP_COACH_DATABASE.bat
git diff --cached --stat
git diff --cached --name-only
git commit -m "Update Coach Studio layout and persistent team setup"
git push
```

These commands are guidance; the installer never runs them. Review any changes
you made locally before installation in the timestamped backup, because this
package is based on the project ZIP you supplied. The backup is outside the
repository. If your current branch has no upstream, set the upstream for the
branch returned by `git branch --show-current` using your normal Git workflow.

For Streamlit Community Cloud, keep the same repository and deployed branch
and select the root entry point `app.py`. Upload changed code, dependencies,
the entire Coach frontend/assets folder and migration SQL files. Keep database
and Gemini settings in Cloud Secrets. A hosted app needs a database reachable
from that host; your laptop's `localhost` PostgreSQL is a different server.
To have local and hosted apps share teams and athlete records, configure both
to use the same hosted PostgreSQL database. Configure its `DATABASE_URL` in
Cloud Secrets and apply the same migrations there if missing. This delivery
does not migrate existing local records to a hosted database.

Official references:
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- https://git-scm.com/docs/gitignore
- https://git-scm.com/docs/git-add

## Verification and limits

This package passed 73 targeted checks: the prior Coach UI/privacy/schema
checks, database-checker checks and installer preservation/rollback checks.
The real app.py entry point rendered Login without a custom launcher. Earlier
browser checks verified Dawn/Dusk, Insights, athlete search, team links and
reviews. A fresh isolated PostgreSQL-compatible persistence test verified that
a team, its description/membership and coach profile survived engine restart;
an individual athlete remained accessible outside any team, and removing team
membership preserved the account and coach connection. The packaging step
checks the complete ZIP, extracts every file and compares its bytes. The
installer is also exercised using the actual full payload against a temporary
project fixture. The checker uses a read-only transaction by default. No access
to your Windows drive, live PostgreSQL records or GitHub
working tree was available here. A successful UI launch alone is not proof
that every save action was exercised against your live database.
