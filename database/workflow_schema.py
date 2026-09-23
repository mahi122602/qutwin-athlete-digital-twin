"""Prepare missing workflow schema once per database identity, before any writes.

This uses the application's configured connection. It never drops data or changes
connection credentials. A denied migration is surfaced as an actionable setup error.
"""
from pathlib import Path
from threading import Lock
import time
from database.connection import get_connection as open_connection

MIGRATION = Path(__file__).parent / 'migrations' / '005_upload_review_workflow.sql'
_lock = Lock()
_verified = {}
TTL = 300

class WorkflowSetupError(RuntimeError):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def _identity(conn):
    details = conn.get_dsn_parameters()
    # Never put passwords into a cache key or error message.
    return tuple(details.get(k, '') for k in ('host','port','dbname','user','options'))


def _missing(cur):
    cur.execute("""SELECT table_name,column_name,is_nullable FROM information_schema.columns
        WHERE table_schema=current_schema() AND table_name IN
        ('qutwin_processed_uploads','qutwin_recommendation_reviews','notifications','digital_athlete_state')""")
    columns = {}
    nullable = {}
    for table, name, is_nullable in cur.fetchall():
        columns.setdefault(table,set()).add(name)
        nullable[(table,name)] = is_nullable
    required = {
        'qutwin_processed_uploads': {'id','athlete_id','content_hash','filename','source','uploaded_at',
            'legacy_upload_id','records','snapshot','events','assignments','processing_status',
            'ai_status','ai_text','ai_model','ai_error','ai_started_at','ai_token'},
        'qutwin_recommendation_reviews': {'id','upload_id','coach_id','status','comment','final_text','reviewed_at'},
        'notifications': {'notification_id','request_id','recipient_role','recipient_id','notification_type','message','is_read','created_at'},
        'digital_athlete_state': {'upload_id','event_type','acwr','recovery_index','environmental_stress',
            'fatigue_index','readiness_index','twin_score','health_index','state_explanation',
            'heart_rate_trend','sleep_trend','training_load_trend','readiness_trend','fatigue_trend',
            'trend_summary','bayesian_fatigue_probability','prediction_confidence','digital_twin_state','user_status_message'},
    }
    absent = {table:sorted(names-columns.get(table,set())) for table,names in required.items()
              if names-columns.get(table,set())}
    if nullable.get(('notifications','request_id')) == 'NO':
        absent.setdefault('notifications',[]).append('nullable request_id')
    return absent


def ensure_schema(conn, force=False):
    key = _identity(conn)
    with _lock:
        if not force and time.monotonic()-_verified.get(key, -TTL) < TTL:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout = '10s'")
                # Serialise schema creation across Streamlit processes/replicas.
                cur.execute("SELECT pg_advisory_xact_lock(713419005)")
                missing = _missing(cur)
                if missing:
                    sql = MIGRATION.read_text(encoding='utf-8')
                    # Caller owns this transaction; strip only standalone wrappers.
                    sql = '\n'.join(line for line in sql.splitlines()
                                    if line.strip().upper() not in ('BEGIN;','COMMIT;'))
                    cur.execute(sql)
                    remaining = _missing(cur)
                    if remaining:
                        raise WorkflowSetupError('Database schema differs from the expected workflow schema. Run migration 005 as the database owner; no upload was saved.', 'schema_mismatch')
            conn.commit()
            _verified[key] = time.monotonic()
        except Exception as exc:
            conn.rollback()
            _verified.pop(key,None)
            if isinstance(exc, WorkflowSetupError):
                raise
            code = getattr(exc,'pgcode',None)
            if code == '42501':
                message = 'Automatic database setup was denied by this database role. Run migration 005 in the Supabase SQL Editor for the same database, then retry.'
            elif code == '42P01':
                message = 'A base application table is missing. Verify that this app connects to your existing QUTwin database before applying migration 005.'
            else:
                message = 'Automatic workflow setup could not finish. Run python -m utils.check_workflow to check the connection and schema.'
            raise WorkflowSetupError(message,code) from exc


def get_connection():
    conn = open_connection()
    try:
        ensure_schema(conn)
        return conn
    except Exception:
        conn.close()
        raise
