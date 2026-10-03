"""Optional athlete-owned training defaults. No effect on uploaded measurements."""
import json
from database.connection import get_connection

DDL = """CREATE TABLE IF NOT EXISTS qutwin_training_locations (
 athlete_id TEXT PRIMARY KEY, preferences JSONB NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
 ALTER TABLE qutwin_training_locations ENABLE ROW LEVEL SECURITY;"""

def preferences(athlete_id, value=None, delete=False):
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '3s'")
            cur.execute(DDL)
            if delete:
                cur.execute("DELETE FROM qutwin_training_locations WHERE athlete_id=%s",(str(athlete_id),))
            elif value is not None:
                cur.execute("""INSERT INTO qutwin_training_locations(athlete_id,preferences)
                    VALUES(%s,%s::jsonb) ON CONFLICT(athlete_id) DO UPDATE
                    SET preferences=EXCLUDED.preferences,updated_at=NOW()""",(str(athlete_id),json.dumps(value,allow_nan=False)))
            cur.execute("SELECT preferences FROM qutwin_training_locations WHERE athlete_id=%s",(str(athlete_id),))
            row=cur.fetchone()
        conn.commit()
        return row[0] if row else {}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
