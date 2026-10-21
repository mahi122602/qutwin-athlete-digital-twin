"""Append numeric assessment revisions without replacing a draft or coach decision."""
from datetime import datetime, timezone
from database.workflow_schema import get_connection
from database.workflow_repository import _rows, json_value
from prediction.assessment_versions import current_assessment, assessment_token
from utils.performance import invalidate_reads


def require_athlete(athlete_id):
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is not None:
        import streamlit as st
        if (not st.session_state.get('logged_in') or st.session_state.get('role') != 'Athlete'
                or str(st.session_state.get('user_id')) != str(athlete_id)):
            raise PermissionError('Only the athlete can update their own assessment inputs.')


@invalidate_reads
def save_assessment(athlete_id, upload_id, expected_token, assessment):
    require_athlete(athlete_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM qutwin_processed_uploads WHERE athlete_id=%s AND id=%s FOR UPDATE',
                        (str(athlete_id), upload_id))
            rows = _rows(cur)
            if not rows:
                raise PermissionError('This saved upload does not belong to this athlete.')
            old = rows[0]
            raw = dict(old.get('snapshot') or {})
            previous = current_assessment(raw)
            if assessment_token(previous) != expected_token:
                raise ValueError('This assessment changed in another session. Reload the page and try again.')
            if old.get('ai_status') == 'generating':
                raise ValueError('Wait for the current recommendation to finish, then save your measurements again.')
            history = list(raw.get('assessment_history') or [])
            history.append(previous)
            updated = dict(assessment, assessment_revision=int(previous.get('assessment_revision', 0)) + 1,
                           assessment_saved_at=datetime.now(timezone.utc).isoformat())
            raw.update(active_assessment=updated, assessment_history=history)
            # Source records, ID, upload date, draft, tokens and coach decisions stay intact.
            cur.execute('UPDATE qutwin_processed_uploads SET snapshot=%s::jsonb,processing_status=%s WHERE id=%s AND athlete_id=%s',
                        (json_value(raw), 'research_estimate' if updated.get('prediction_status') == 'research_estimate'
                         else 'observations_only', upload_id, str(athlete_id)))
        conn.commit()
        return {'status': 'saved', 'id': upload_id, 'updated_existing': True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
