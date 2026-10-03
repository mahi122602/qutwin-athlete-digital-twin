"""Fresh authorization on each athlete-specific UI data read (before caches)."""
from functools import wraps
from database.connection import get_connection

def require_coach_connection(coach_id,athlete_id):
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM coach_athlete_mapping WHERE coach_id=%s AND athlete_id=%s',(str(coach_id),str(athlete_id)))
            if not cur.fetchone():raise PermissionError('This athlete is not currently connected to you.')
    finally:conn.close()

def guard_athlete_read(function):
    @wraps(function)
    def wrapped(athlete_id,*args,**kwargs):
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        coach_actor=None
        if get_script_run_ctx(suppress_warning=True) is not None:
            import streamlit as st
            actor=str(st.session_state.get('user_id') or '')
            if not st.session_state.get('logged_in'):raise PermissionError('Please sign in.')
            if st.session_state.get('role')=='Coach':
                require_coach_connection(actor,athlete_id)
                coach_actor=actor
            elif st.session_state.get('role')!='Athlete' or actor!=str(athlete_id):raise PermissionError('This is not your athlete account.')
        result=function(athlete_id,*args,**kwargs)
        if coach_actor is not None:require_coach_connection(coach_actor,athlete_id)
        return result
    return wrapped

def guard_private_health(function):
    @wraps(function)
    def wrapped(athlete_id,*args,**kwargs):
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is not None:
            import streamlit as st
            if not st.session_state.get('logged_in') or st.session_state.get('role')!='Athlete' or str(st.session_state.get('user_id'))!=str(athlete_id):
                raise PermissionError('Period records are private to the athlete.')
        return function(athlete_id,*args,**kwargs)
    return wrapped
