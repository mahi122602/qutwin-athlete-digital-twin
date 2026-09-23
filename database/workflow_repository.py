"""Atomic uploads and per-upload coach decisions. Never cache across page visits."""
import json
import uuid
import pandas as pd
from database.workflow_schema import get_connection
from utils.performance import invalidate_reads


def json_value(value):
    if isinstance(value, pd.DataFrame):
        return value.to_json(orient="records", date_format="iso")
    return json.dumps(value, default=str, allow_nan=False)


def _rows(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def list_uploads(athlete_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM qutwin_processed_uploads WHERE athlete_id=%s ORDER BY uploaded_at DESC,id DESC", (str(athlete_id),))
            return _rows(cur)
    finally:
        conn.close()


def _notify(cur, role, recipient, kind, message):
    cur.execute("""INSERT INTO notifications(recipient_role,recipient_id,notification_type,message,is_read)
        VALUES(%s,%s,%s,%s,FALSE)""", (str(role).title(), str(recipient), kind, message))


@invalidate_reads
def save_upload(athlete_id, filename, source, content_hash, records, snapshot, events, assignments, processing_status, states=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            legacy_id = None
            original_date = None
            adopted = False
            cur.execute("SELECT to_regclass('qutwin_upload_events'),to_regclass('qutwin_daily_uploads')")
            old_events, old_daily = cur.fetchone()
            if old_events:
                cur.execute("""SELECT e.upload_id,COALESCE(
                    to_jsonb(u)->>'uploaded_at', to_jsonb(u)->>'created_at',
                    to_jsonb(u)->>'upload_date', to_jsonb(e)->>'created_at')
                    FROM qutwin_upload_events e
                    JOIN uploaded_files u ON u.upload_id=e.upload_id WHERE e.athlete_id=%s AND e.content_hash=%s""",
                    (str(athlete_id),content_hash))
                old = cur.fetchone()
                if old:
                    legacy_id, original_date = old
                    adopted = True
            if old_daily and original_date is None:
                cur.execute("SELECT created_at FROM qutwin_daily_uploads WHERE athlete_id=%s AND content_hash=%s",(str(athlete_id),content_hash))
                old = cur.fetchone()
                if old:
                    original_date = old[0]
                    adopted = True
            cur.execute("""INSERT INTO qutwin_processed_uploads
                (athlete_id,filename,source,content_hash,records,snapshot,events,assignments,processing_status)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s)
                ON CONFLICT(athlete_id,content_hash) DO NOTHING RETURNING id""",
                (str(athlete_id),filename,source,content_hash,json_value(records),json_value(snapshot),json_value(events),json_value(assignments),processing_status))
            row=cur.fetchone()
            if row is None:
                cur.execute("SELECT id FROM qutwin_processed_uploads WHERE athlete_id=%s AND content_hash=%s",(str(athlete_id),content_hash))
                return {"status":"already_saved", "id":cur.fetchone()[0]}
            workflow_id=row[0]
            if original_date is not None:
                # Adopt a previously saved file rather than adding another History row.
                cur.execute("UPDATE qutwin_processed_uploads SET uploaded_at=%s,legacy_upload_id=%s WHERE id=%s",(original_date,legacy_id,workflow_id))
            if adopted and original_date is None:
                # Keep the original file link even if its legacy save time was never recorded.
                cur.execute("UPDATE qutwin_processed_uploads SET legacy_upload_id=%s, snapshot=snapshot || %s::jsonb WHERE id=%s",(legacy_id,json.dumps({'legacy_upload_time_unknown':True}),workflow_id))
            if not adopted and states is not None and not states.empty:
                from database.activity_upload_repository import _insert_states
                cur.execute("INSERT INTO uploaded_files(athlete_id,filename,file_type,rows_extracted) VALUES(%s,%s,%s,%s) RETURNING upload_id",(athlete_id,filename,source,len(records)))
                legacy_id=cur.fetchone()[0]
                _insert_states(cur,athlete_id,legacy_id,states)
                cur.execute("UPDATE qutwin_processed_uploads SET legacy_upload_id=%s WHERE id=%s",(legacy_id,workflow_id))
            conn.commit()
            return {"status":"already_saved" if adopted else "saved","id":workflow_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def claim_ai(athlete_id, upload_id):
    conn=get_connection()
    token=str(uuid.uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE qutwin_processed_uploads SET ai_status='generating',ai_token=%s,ai_started_at=NOW(),ai_error=NULL
                WHERE id=%s AND athlete_id=%s AND (ai_status IN ('pending','not_configured')
                OR (ai_status='failed' AND (ai_started_at IS NULL OR ai_started_at < NOW()-INTERVAL '5 minutes'))
                OR (ai_status='generating' AND ai_started_at < NOW()-INTERVAL '2 minutes')) RETURNING *""",(token,upload_id,str(athlete_id)))
            rows=_rows(cur)
        conn.commit()
        return (rows[0],token) if rows else (None,None)
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


@invalidate_reads
def finish_ai(athlete_id, upload_id, token, text=None, model=None, error=None, status='failed'):
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE qutwin_processed_uploads SET ai_status=%s,ai_text=%s,ai_model=%s,ai_error=%s
                WHERE id=%s AND athlete_id=%s AND ai_token=%s AND ai_status='generating' RETURNING id""",
                ('ready' if text else status,text,model,error,upload_id,str(athlete_id),token))
            if cur.fetchone() and text:
                cur.execute("SELECT coach_id FROM coach_athlete_mapping WHERE athlete_id=%s",(str(athlete_id),))
                coaches=[r[0] for r in cur.fetchall()]
                for coach in coaches:
                    cur.execute("""INSERT INTO qutwin_recommendation_reviews(upload_id,coach_id) VALUES(%s,%s)
                        ON CONFLICT(upload_id,coach_id) DO NOTHING RETURNING id""",(upload_id,str(coach)))
                    if cur.fetchone():
                        _notify(cur,'coach',coach,'AI Recommendation Review',f'A new AI recommendation for athlete {athlete_id}, upload #{upload_id}, awaits your review. Open Recommendation Reviews.')
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def get_reviews(athlete_id):
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.* FROM qutwin_recommendation_reviews r
                JOIN qutwin_processed_uploads u ON u.id=r.upload_id WHERE u.athlete_id=%s
                ORDER BY r.reviewed_at DESC NULLS LAST,r.id DESC""",(str(athlete_id),))
            return _rows(cur)
    finally:
        conn.close()


def coach_queue(coach_id):
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            # Also make earlier, unassigned uploads available after a new connection.
            cur.execute("""INSERT INTO qutwin_recommendation_reviews(upload_id,coach_id)
                SELECT u.id,%s FROM qutwin_processed_uploads u JOIN coach_athlete_mapping m
                ON m.athlete_id::text=u.athlete_id WHERE m.coach_id=%s AND u.ai_status='ready'
                ON CONFLICT(upload_id,coach_id) DO NOTHING""",(str(coach_id),str(coach_id)))
            cur.execute("""SELECT r.*,u.athlete_id,u.filename,u.uploaded_at,u.snapshot,u.events,u.ai_text,u.ai_model
                FROM qutwin_recommendation_reviews r JOIN qutwin_processed_uploads u ON u.id=r.upload_id
                JOIN coach_athlete_mapping m ON m.athlete_id::text=u.athlete_id AND m.coach_id::text=r.coach_id
                WHERE r.coach_id=%s ORDER BY (r.status='Pending') DESC,u.uploaded_at DESC,r.id DESC""",(str(coach_id),))
            result=_rows(cur)
        conn.commit(); return result
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


@invalidate_reads
def review_recommendation(coach_id, review_id, decision, comment):
    if decision not in ('Approved','Rejected','Modified'):
        raise ValueError('Invalid review decision.')
    comment=str(comment or '').strip()
    if decision in ('Rejected','Modified') and not comment:
        raise ValueError('Provide a reason for rejection or your revised recommendation.')
    if len(comment)>12000:
        raise ValueError('Please keep feedback under 12,000 characters.')
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.upload_id,u.athlete_id,u.ai_text FROM qutwin_recommendation_reviews r
                JOIN qutwin_processed_uploads u ON u.id=r.upload_id
                JOIN coach_athlete_mapping m ON m.athlete_id::text=u.athlete_id AND m.coach_id::text=r.coach_id
                WHERE r.id=%s AND r.coach_id=%s AND r.status='Pending' FOR UPDATE OF r""",(review_id,str(coach_id)))
            row=cur.fetchone()
            if row is None:
                raise ValueError('This review was already completed or is not assigned to you.')
            upload_id,athlete_id,ai_text=row
            final=ai_text if decision=='Approved' else comment if decision=='Modified' else None
            cur.execute("UPDATE qutwin_recommendation_reviews SET status=%s,comment=%s,final_text=%s,reviewed_at=NOW() WHERE id=%s",(decision,comment,final,review_id))
            _notify(cur,'athlete',athlete_id,'Coach Recommendation',f'Coach {coach_id} {decision.lower()} the recommendation for upload #{upload_id}. Open Predictions & Coach Recommendations for feedback and details.')
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


@invalidate_reads
def correct_observation_upload(athlete_id, filename, source, content_hash, records, snapshot, events, assignments, processing_status, states=None):
    """Replace unassessed observations atomically; preserve the upload ID and date."""
    conn=get_connection()
    existing=None
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM qutwin_processed_uploads WHERE athlete_id=%s AND content_hash=%s FOR UPDATE',(str(athlete_id),content_hash))
            rows=_rows(cur)
            if rows:
                existing=rows[0]
                cur.execute('SELECT id FROM qutwin_recommendation_reviews WHERE upload_id=%s',(existing['id'],))
                reviewed=cur.fetchone()
                if existing['processing_status']!='observations_only' or existing.get('legacy_upload_id') or existing.get('ai_text') or existing['ai_status']=='generating' or reviewed:
                    raise ValueError('This saved file already has predictions or an AI/coach review. Its assessment cannot be overwritten by import corrections.')
                legacy_id=None
                if states is not None and not states.empty:
                    from database.activity_upload_repository import _insert_states
                    cur.execute('INSERT INTO uploaded_files(athlete_id,filename,file_type,rows_extracted) VALUES(%s,%s,%s,%s) RETURNING upload_id',(athlete_id,filename,source,len(records)))
                    legacy_id=cur.fetchone()[0]
                    _insert_states(cur,athlete_id,legacy_id,states)
                cur.execute("""UPDATE qutwin_processed_uploads SET records=%s::jsonb,snapshot=%s::jsonb,
                    events=%s::jsonb,assignments=%s::jsonb,processing_status=%s,legacy_upload_id=%s,
                    ai_status='pending',ai_error=NULL,ai_token=NULL,ai_started_at=NULL WHERE id=%s""",
                    (json_value(records),json_value(snapshot),json_value(events),json_value(assignments),processing_status,legacy_id,existing['id']))
        conn.commit()
    except Exception:
        conn.rollback();raise
    finally:
        conn.close()
    if existing:return {'status':'saved','id':existing['id'],'updated_existing':True}
    return save_upload(athlete_id,filename,source,content_hash,records,snapshot,events,assignments,processing_status,states)


@invalidate_reads
def refresh_unreviewed_analysis(athlete_id, filename, source, content_hash, records, snapshot, events, assignments, processing_status, states=None):
    """Explicit version upgrade, preserving date/ID and the previous assessment.
    An existing AI draft or coach review is immutable through this operation.
    """
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM qutwin_processed_uploads WHERE athlete_id=%s AND content_hash=%s FOR UPDATE',(str(athlete_id),content_hash))
            rows=_rows(cur)
            if not rows:raise ValueError('Saved upload could not be found for this athlete.')
            old=rows[0]
            cur.execute('SELECT id FROM qutwin_recommendation_reviews WHERE upload_id=%s',(old['id'],))
            if old.get('ai_text') or old.get('ai_status')=='generating' or cur.fetchone():
                raise ValueError('An existing AI draft or coach review cannot be overwritten. This upload retains its original assessment.')
            if old['snapshot'].get('model_version')==snapshot.get('model_version') and old['processing_status']!='observations_only':
                raise ValueError('This saved file already has predictions from this version and cannot be overwritten.')
            previous=dict(old['snapshot']);previous.pop('previous_assessment',None)
            updated=dict(snapshot,previous_assessment=previous)
            cur.execute("""UPDATE qutwin_processed_uploads SET snapshot=%s::jsonb,processing_status=%s,
                ai_status='pending',ai_error=NULL,ai_token=NULL,ai_started_at=NULL WHERE id=%s""",
                (json_value(updated),processing_status,old['id']))
        conn.commit()
        return {'status':'saved','id':old['id'],'updated_existing':True}
    except Exception:
        conn.rollback();raise
    finally:conn.close()
