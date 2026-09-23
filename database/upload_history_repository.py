"""One row per file, merging legacy uploads without duplicating new uploads."""
import pandas as pd
from database.connection import get_connection
from database.workflow_repository import list_uploads, get_reviews


def get_upload_history(athlete_id):
    uploads=list_uploads(athlete_id)
    reviews=get_reviews(athlete_id)
    records=[]
    for u in uploads:
        feedback=[r for r in reviews if r['upload_id']==u['id']]
        coach='; '.join(f"{r['coach_id']}: {r['status']} — {r.get('final_text') or r.get('comment') or 'Awaiting review'}" for r in feedback)
        records.append(dict(u['snapshot'], _uploaded_at=None if u['snapshot'].get('legacy_upload_time_unknown') else u['uploaded_at'],filename=u['filename'],source=u['source'],
            rows_extracted=len(u['records']),upload_status=u['processing_status'],workflow_id=u['id'],
            events=', '.join(u['events']),recommendation=u.get('ai_text') or u.get('ai_error') or 'AI generation pending',
            coach_feedback=coach or 'Awaiting AI generation or coach assignment'))
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('uploaded_files'),to_regclass('digital_athlete_state'),to_regclass('qutwin_daily_uploads')")
            legacy,states,daily=cur.fetchone()
            if legacy:
                # JSON key access tolerates legacy installations with no upload_id
                # on their old state table. Never borrow another upload's state.
                state_sql="""(SELECT to_jsonb(s) FROM digital_athlete_state s
                    WHERE to_jsonb(s)->>'upload_id'=u.upload_id::text AND s.athlete_id=u.athlete_id
                    ORDER BY s.timestamp DESC NULLS LAST LIMIT 1)""" if states else 'NULL'
                cur.execute(f"""SELECT COALESCE(to_jsonb(u)->>'uploaded_at',to_jsonb(u)->>'created_at',
                    to_jsonb(u)->>'upload_date'),u.filename,u.file_type,u.rows_extracted,{state_sql}
                    FROM uploaded_files u WHERE u.athlete_id=%s AND NOT EXISTS
                    (SELECT 1 FROM qutwin_processed_uploads w WHERE w.legacy_upload_id=u.upload_id AND w.athlete_id=%s)""",(str(athlete_id),str(athlete_id)))
                for date,name,source,count,state in cur.fetchall():
                    records.append(dict(state or {},_uploaded_at=date,filename=name,source=source,rows_extracted=count,
                        upload_status='Legacy saved upload',coach_feedback='Legacy upload — no linked review'))
            if daily:
                cur.execute("""SELECT d.created_at,d.filename FROM qutwin_daily_uploads d WHERE d.athlete_id=%s
                    AND NOT EXISTS(SELECT 1 FROM qutwin_processed_uploads w WHERE w.athlete_id=d.athlete_id AND w.content_hash=d.content_hash)""",(str(athlete_id),))
                for date,name in cur.fetchall():
                    records.append(dict(_uploaded_at=date,filename=name,source='Samsung daily summary',upload_status='Legacy observations only'))
    finally:
        conn.close()
    frame=pd.DataFrame(records)
    if not frame.empty:
        frame['_uploaded_at']=pd.to_datetime(frame['_uploaded_at'],utc=True,errors='coerce',format='mixed')
        frame=frame.sort_values('_uploaded_at',ascending=False,kind='stable').reset_index(drop=True)
    return frame
