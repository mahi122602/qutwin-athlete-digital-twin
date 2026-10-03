"""Account-scoped, transactional privacy operations for the Streamlit app."""
from psycopg2 import sql
from database.connection import get_connection
from authentication.password_utils import check_password
from utils.performance import invalidate_reads

def _athlete_actor():
    import streamlit as st
    if not st.session_state.get('logged_in') or st.session_state.get('role')!='Athlete' or not st.session_state.get('user_id'):
        raise PermissionError('Sign in to your athlete account first.')
    return str(st.session_state.user_id)

def connected_coaches():
    athlete_id=_athlete_actor();conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT c.coach_id,c.name FROM coaches c JOIN coach_athlete_mapping m ON m.coach_id=c.coach_id WHERE m.athlete_id=%s ORDER BY c.name',(athlete_id,))
            return cur.fetchall()
    finally:conn.close()

@invalidate_reads
def disconnect_coach(coach_id):
    athlete_id=_athlete_actor();conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT athlete_id FROM athletes WHERE athlete_id=%s FOR UPDATE',(athlete_id,))
            if not cur.fetchone():raise PermissionError('Account no longer exists.')
            # Pending requests cannot reconnect the pair after disconnection.
            cur.execute("UPDATE connection_requests SET status='Rejected',responded_at=CURRENT_TIMESTAMP WHERE athlete_id=%s AND coach_id=%s AND status='Pending'",(athlete_id,str(coach_id)))
            cur.execute('DELETE FROM coach_athlete_mapping WHERE athlete_id=%s AND coach_id=%s',(athlete_id,str(coach_id)))
        conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()

def deletion_order(tables,edges):
    """Children first. Unknown dependency cycles fail closed."""
    remaining=set(tables);out=[]
    while remaining:
        ready=sorted(t for t in remaining if not any(parent==t and child in remaining and child!=t for child,parent in edges))
        if not ready:raise ValueError('Related tables need an administrator-reviewed deletion migration.')
        out.extend(ready);remaining.difference_update(ready)
    return out

@invalidate_reads
def delete_my_account(password,confirmation):
    athlete_id=_athlete_actor()
    if confirmation!='DELETE':raise ValueError('Type DELETE to confirm.')
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT password FROM athletes WHERE athlete_id=%s FOR UPDATE',(athlete_id,))
            row=cur.fetchone()
            if not row or not check_password(password,row[0]):raise ValueError('Your current password is incorrect.')
            # Include version-specific tables with no FK, such as uploads and cycle logs.
            cur.execute("SELECT c.table_name,c.column_name FROM information_schema.columns c JOIN information_schema.tables t ON t.table_schema=c.table_schema AND t.table_name=c.table_name WHERE c.table_schema='public' AND t.table_type='BASE TABLE'")
            cols={}
            for table,column in cur.fetchall():cols.setdefault(table,set()).add(column)
            tables={t for t,c in cols.items() if 'athlete_id' in c}
            cur.execute("""SELECT c.relname,p.relname FROM pg_constraint fk
                JOIN pg_class c ON c.oid=fk.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
                JOIN pg_class p ON p.oid=fk.confrelid
                WHERE fk.contype='f' AND n.nspname='public'""")
            edges=cur.fetchall()
            if 'notifications' in cols:
                if 'connection_requests' in cols:
                    cur.execute('DELETE FROM notifications WHERE request_id IN (SELECT request_id FROM connection_requests WHERE athlete_id=%s)',(athlete_id,))
                cur.execute("DELETE FROM notifications WHERE notification_type='AI Recommendation Review' AND strpos(message,%s)>0",('for athlete '+athlete_id+', upload #',))
                cur.execute("DELETE FROM notifications WHERE LOWER(recipient_role)='athlete' AND recipient_id=%s",(athlete_id,))
            if 'qutwin_recommendation_reviews' in cols and 'qutwin_processed_uploads' in cols:
                cur.execute('DELETE FROM qutwin_recommendation_reviews WHERE upload_id IN (SELECT id FROM qutwin_processed_uploads WHERE athlete_id=%s)',(athlete_id,))
            # Explicit dependency for legacy schemas without a foreign key.
            edges.append(('digital_athlete_state','uploaded_files'))
            for table in deletion_order(tables-{'athletes'},edges):
                cur.execute(sql.SQL('DELETE FROM public.{} WHERE athlete_id=%s').format(sql.Identifier(table)),(athlete_id,))
            cur.execute('DELETE FROM athletes WHERE athlete_id=%s',(athlete_id,))
            if cur.rowcount!=1:raise RuntimeError('Account deletion could not be completed.')
        conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()
