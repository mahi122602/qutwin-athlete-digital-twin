"""Prepare the additive coach tables in the database the app actually uses."""
from pathlib import Path
from threading import Lock
import time
from database.workflow_schema import get_connection as workflow_connection, _identity

_lock = Lock()
_verified = {}
_required = {
    'qutwin_coach_profiles': {'coach_id', 'email', 'organisation', 'specialties'},
    'qutwin_coach_teams': {'id', 'coach_id', 'name', 'description'},
    'qutwin_team_members': {'team_id', 'coach_id', 'athlete_id'},
}


class CoachSetupError(RuntimeError):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def _missing(cur):
    cur.execute("""SELECT table_name,column_name FROM information_schema.columns
        WHERE table_schema=current_schema() AND table_name=ANY(%s)""", (list(_required),))
    columns = {}
    for table, column in cur.fetchall():
        columns.setdefault(table, set()).add(column)
    return {table: sorted(names - columns.get(table, set()))
            for table, names in _required.items() if names - columns.get(table, set())}


def ensure_schema(conn, force=False):
    identity = _identity(conn)
    with _lock:
        if not force and time.monotonic() - _verified.get(identity, -300) < 300:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout = '10s'")
                cur.execute('SELECT pg_advisory_xact_lock(713419008)')
                missing = _missing(cur)
                if missing:
                    # Do not create a new empty base application in the wrong DB.
                    cur.execute("SELECT to_regclass('coaches'),to_regclass('athletes'),to_regclass('coach_athlete_mapping')")
                    if any(value is None for value in cur.fetchone()):
                        raise CoachSetupError('The connected database is missing the existing QUTwin account tables. Check the database configuration.', 'base_schema_missing')
                    sql = (Path(__file__).parent / 'migrations' / '008_coach_studio.sql').read_text()
                    sql = '\n'.join(line for line in sql.splitlines()
                                    if line.strip().upper() not in ('BEGIN;', 'COMMIT;'))
                    cur.execute(sql)
                    if _missing(cur):
                        raise CoachSetupError('Coach tables exist but their columns differ from this version. Use the troubleshooting check to identify the difference.', 'schema_mismatch')
            conn.commit()
            _verified[identity] = time.monotonic()
        except Exception as exc:
            conn.rollback()
            _verified.pop(identity, None)
            if isinstance(exc, CoachSetupError):
                raise
            code = getattr(exc, 'pgcode', None)
            raise CoachSetupError('Coach database setup could not finish. Apply migration 008 to the database this running app uses, using its database owner.', code) from exc


def get_connection():
    conn = workflow_connection()
    try:
        ensure_schema(conn)
        return conn
    except Exception:
        conn.close()
        raise
