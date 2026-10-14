"""Coach-owned teams and lifecycle; never delete athlete accounts on disconnect."""
from database.coach_schema import get_connection
from database.coach_identity import actor, _save_details
from authentication.password_utils import check_password
from utils.performance import invalidate_reads

def rows(cur):return [dict(zip([c[0] for c in cur.description],r)) for r in cur.fetchall()]
def query(statement,params=()):
    actor('Coach');conn=get_connection()
    try:
        with conn.cursor() as cur:cur.execute(statement,params);return rows(cur)
    finally:conn.close()
def profile():
    _,uid=actor('Coach');data=query('SELECT coach_id,name FROM coaches WHERE coach_id=%s',(uid,))
    if not data:raise PermissionError('This coach account no longer exists.')
    return data[0]
def roster():
    _,uid=actor('Coach')
    return query('''SELECT a.athlete_id,a.name,u.id AS upload_id,u.filename,u.uploaded_at,u.snapshot,u.ai_status,COALESCE(t.names,'') AS teams
    FROM coach_athlete_mapping m JOIN athletes a ON a.athlete_id=m.athlete_id
    LEFT JOIN LATERAL(SELECT id,filename,uploaded_at,snapshot,ai_status FROM qutwin_processed_uploads WHERE athlete_id=a.athlete_id::text ORDER BY uploaded_at DESC,id DESC LIMIT 1) u ON TRUE
    LEFT JOIN LATERAL(SELECT string_agg(ct.name,', ' ORDER BY ct.name) AS names FROM qutwin_team_members tm JOIN qutwin_coach_teams ct ON ct.id=tm.team_id WHERE tm.coach_id=m.coach_id::text AND tm.athlete_id=a.athlete_id::text) t ON TRUE
    WHERE m.coach_id=%s ORDER BY a.name,a.athlete_id''',(uid,))
def teams():
    _,uid=actor('Coach');return query('SELECT id,name,description FROM qutwin_coach_teams WHERE coach_id=%s ORDER BY id',(uid,))
def members(team_id):
    _,uid=actor('Coach');return query('SELECT athlete_id FROM qutwin_team_members WHERE coach_id=%s AND team_id=%s',(uid,team_id))
@invalidate_reads
def create_team(name,description=''):
    _,uid=actor('Coach');name=name.strip()
    if not 1<=len(name)<=100:raise ValueError('Enter a team name of 1–100 characters.')
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO qutwin_coach_teams(coach_id,name,description) VALUES(%s,%s,%s) RETURNING id',(uid,name,description[:2000]));result=cur.fetchone()[0]
        conn.commit();return result
    except Exception:conn.rollback();raise
    finally:conn.close()
@invalidate_reads
def change_member(team_id,athlete_id,add=True):
    _,uid=actor('Coach');conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM qutwin_coach_teams WHERE id=%s AND coach_id=%s FOR UPDATE',(team_id,uid))
            if not cur.fetchone():raise PermissionError('This team is not yours.')
            if add:
                cur.execute('SELECT 1 FROM coach_athlete_mapping WHERE coach_id=%s AND athlete_id=%s FOR SHARE',(uid,str(athlete_id)))
                if not cur.fetchone():raise PermissionError('Connect with this athlete first.')
                cur.execute('INSERT INTO qutwin_team_members(team_id,coach_id,athlete_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(team_id,uid,str(athlete_id)))
            else:cur.execute('DELETE FROM qutwin_team_members WHERE team_id=%s AND coach_id=%s AND athlete_id=%s',(team_id,uid,str(athlete_id)))
        conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()
@invalidate_reads
def disconnect(athlete_id):
    _,uid=actor('Coach');conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE connection_requests SET status='Rejected',responded_at=NOW() WHERE coach_id=%s AND athlete_id=%s AND status='Pending'",(uid,str(athlete_id)))
            cur.execute('DELETE FROM coach_athlete_mapping WHERE coach_id=%s AND athlete_id=%s',(uid,str(athlete_id)))
        conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()
@invalidate_reads
def save_profile(name,details):
    _,uid=actor('Coach')
    if not 1<=len(name.strip())<=100:raise ValueError('Enter your name (up to 100 characters).')
    conn=get_connection()
    try:
        with conn.cursor() as cur:cur.execute('UPDATE coaches SET name=%s WHERE coach_id=%s',(name.strip(),uid));_save_details(cur,'Coach',uid,details)
        conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()
@invalidate_reads
def delete_profile(password,confirmation):
    _,uid=actor('Coach')
    if confirmation!='DELETE':raise ValueError('Type DELETE to confirm.')
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT password FROM coaches WHERE coach_id=%s FOR UPDATE',(uid,));row=cur.fetchone()
            if not row or not check_password(password,row[0]):raise ValueError('Your current password is incorrect.')
            cur.execute("DELETE FROM notifications WHERE request_id IN (SELECT request_id FROM connection_requests WHERE coach_id=%s) OR (LOWER(recipient_role)='coach' AND recipient_id=%s)",(uid,uid))
            cur.execute('DELETE FROM connection_requests WHERE coach_id=%s',(uid,))
            cur.execute('DELETE FROM coach_athlete_mapping WHERE coach_id=%s',(uid,))
            cur.execute('DELETE FROM qutwin_coach_teams WHERE coach_id=%s',(uid,))
            cur.execute('DELETE FROM qutwin_coach_profiles WHERE coach_id=%s',(uid,))
            cur.execute("DELETE FROM qutwin_recommendation_reviews WHERE coach_id=%s AND status='Pending'",(uid,))
            cur.execute("UPDATE qutwin_recommendation_reviews SET coach_id=%s WHERE coach_id=%s",('Deleted coach '+__import__('uuid').uuid4().hex,uid))
            cur.execute("SELECT to_regclass('public.coach_recommendations')")
            if cur.fetchone()[0]:cur.execute('UPDATE coach_recommendations SET coach_id=NULL WHERE coach_id=%s',(uid,))
            cur.execute('DELETE FROM coaches WHERE coach_id=%s',(uid,))
        conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()
