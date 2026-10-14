"""Live-data presentation for the approved trackside coach home."""
from pathlib import Path
import logging
import streamlit as st
import streamlit.components.v1 as components
from database import coach_studio as db
from database.workflow_repository import coach_queue
from database.connection_request_repository import get_unread_notification_count
from database.access_control import require_coach_connection
from ui.coach_shell import go

_root = Path(__file__).with_name('coach_dashboard_frontend')
_dashboard = components.declare_component('qutwin_coach_dashboard', path=str(_root))
log = logging.getLogger(__name__)


def resolve_action(event, athletes, teams, reviews=()):
    if not isinstance(event, dict) or not isinstance(event.get('nonce'), str):
        return None
    action = event.get('action')
    if action in {'athletes', 'teams', 'reviews', 'connections', 'notifications'}:
        return {'page': {'athletes':'Athletes','teams':'Teams','reviews':'Reviews',
                         'connections':'Connections','notifications':'Notifications'}[action]}
    if action == 'attention' and event.get('level') in {'High','Medium','Low','Not assessed'}:
        return {'page':'Athletes', 'level':event['level']}
    if action == 'athlete' and str(event.get('athlete_id')) in {str(x['athlete_id']) for x in athletes}:
        return {'page':'Athlete Detail', 'athlete':str(event['athlete_id'])}
    if action == 'team' and str(event.get('team_id')) in {str(x['id']) for x in teams}:
        return {'page':'Team Detail', 'team':int(event['team_id'])}
    if action == 'review':
        row = next((x for x in reviews if str(x['upload_id']) == str(event.get('upload_id'))), None)
        if row and str(row['athlete_id']) in {str(x['athlete_id']) for x in athletes}:
            return {'page':'Reviews', 'athlete':str(row['athlete_id']), 'upload':int(row['upload_id'])}
    return None


def render_dashboard(roster, classify):
    uid = str(st.session_state.user_id)
    unavailable = []
    try:
        teams = db.teams()
        team_count = len(teams)
        presented_teams = []
        for team in teams:
            ids = {str(x['athlete_id']) for x in db.members(team['id'])}
            group = [x for x in roster if str(x['athlete_id']) in ids]
            counts = {level:sum(classify(x.get('snapshot')) == level for x in group)
                      for level in ('High','Medium','Low','Not assessed')}
            presented_teams.append(dict(id=team['id'], name=team['name'], count=len(group), counts=counts))
    except Exception:
        log.exception('Coach team summary failed')
        teams, presented_teams = [], []
        team_count = None
        unavailable.append('Teams could not be loaded.')
    try:
        queue = [x for x in coach_queue(uid) if x['status'] == 'Pending']
        waiting = len(queue)
    except Exception:
        log.exception('Coach review summary failed')
        queue, waiting = [], None
        unavailable.append('The review queue could not be loaded.')
    try:
        unread = get_unread_notification_count('Coach', uid)
    except Exception:
        unread = None
    names = {str(x['athlete_id']):x['name'] for x in roster}
    inbox = [{'athlete_id':str(x['athlete_id']), 'name':names.get(str(x['athlete_id']), 'Connected athlete'),
              'label':'AI draft awaiting review', 'upload_id':x['upload_id']}
             for x in queue[:2]]
    counts = {level:sum(classify(x.get('snapshot')) == level for x in roster)
              for level in ('High','Medium','Low','Not assessed')}
    model = dict(name=st.session_state.coach_display_name,
        theme=st.session_state.get('studio_theme_'+uid, 'dawn'),
        counts=counts, athlete_count=len(roster), team_count=team_count,
        waiting=waiting, unread=unread, teams=presented_teams, inbox=inbox,
        athletes=[dict(athlete_id=str(x['athlete_id']),name=x['name'],attention=classify(x.get('snapshot')))
                  for x in roster], unavailable=unavailable)
    event = _dashboard(model=model, key='coach_home_'+uid, default=None)
    seen = 'coach_home_event_'+uid
    if not isinstance(event, dict) or event.get('nonce') == st.session_state.get(seen):
        return
    action = resolve_action(event, roster, teams, queue)
    if not action:
        return
    if action.get('athlete'):
        require_coach_connection(uid, action['athlete'])
    if action.get('level'):
        st.session_state.coach_attention_filter = action['level']
    st.session_state[seen] = event['nonce']
    if event.get('action') == 'athlete':
        st.session_state.cs_detail_tab = 'Overview'
    go(action['page'], action.get('athlete'), action.get('team'), action.get('upload'))
    st.rerun()
