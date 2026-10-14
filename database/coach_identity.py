"""Owner-only coach identity and optional profile metadata."""
from database.connection import get_connection

def actor(role='Coach'):
    import streamlit as st
    uid=st.session_state.get('user_id')
    if not st.session_state.get('logged_in') or st.session_state.get('role')!=role or not uid:
        raise PermissionError('Sign in to your coach account.')
    return role,str(uid)

def _save_details(cur,role,uid,d):
    if role!='Coach':raise PermissionError('Coach profile required.')
    cur.execute('''INSERT INTO qutwin_coach_profiles(coach_id,email,organisation,specialties)
        VALUES(%s,%s,%s,%s) ON CONFLICT(coach_id) DO UPDATE SET
        email=EXCLUDED.email,organisation=EXCLUDED.organisation,
        specialties=EXCLUDED.specialties,updated_at=NOW()''',
        (uid,str(d.get('email',''))[:255],str(d.get('organisation',''))[:200],str(d.get('specialties',''))[:500]))

def my_details():
    _,uid=actor();conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT email,organisation,specialties FROM qutwin_coach_profiles WHERE coach_id=%s',(uid,));r=cur.fetchone()
            return dict(zip(['email','organisation','specialties'],r)) if r else {}
    finally:conn.close()
