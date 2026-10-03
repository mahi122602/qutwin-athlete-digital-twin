"""Digital Training Studio home, integrated with the existing authenticated router."""
import logging
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from ui.studio_model import build_studio_model, resolve_action

_FRONTEND = Path(__file__).resolve().parents[2] / 'ui' / 'studio_frontend'
_studio = components.declare_component('qutwin_training_studio', path=str(_FRONTEND))
log = logging.getLogger(__name__)


def render_studio():
    from database.athlete_repository import get_athlete_profile
    from database.connection_request_repository import get_unread_notification_count
    from database.studio_repository import get_studio_records, get_studio_forecast
    athlete_id = str(st.session_state.user_id)
    errors = []
    try: profile = get_athlete_profile(athlete_id)
    except Exception:
        log.exception('Studio profile load failed'); profile = {}; errors.append('profile')
    try: uploads, reviews = get_studio_records(athlete_id)
    except Exception:
        log.exception('Studio activity load failed'); uploads, reviews = [], []; errors.extend(['uploads','reviews'])
    try: unread = get_unread_notification_count('Athlete', athlete_id)
    except Exception:
        log.exception('Studio notification count failed'); unread = 0; errors.append('notifications')
    try: forecast = get_studio_forecast(athlete_id)
    except Exception:
        log.exception('Studio forecast load failed'); forecast = None; errors.append('forecast')
    model = build_studio_model(profile, uploads, reviews, unread, errors)
    from ui.studio_summary import build_summary
    model['summary'] = build_summary(uploads[0] if uploads else None, reviews, forecast, errors)
    theme_key = 'studio_theme_' + athlete_id
    model['theme'] = st.session_state.get(theme_key, 'dawn')
    background = '#111e21' if model['theme'] == 'dusk' else '#fcfaf4'
    # These styles exist only while this page is mounted; all other page themes stay intact.
    st.markdown('''<style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {background:#fcfaf4!important;}
    header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
    .dashboard-orb, footer {display:none!important;}
    .block-container, [data-testid="stMainBlockContainer"] {max-width:100%!important;padding:0!important;}
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {gap:0!important;}
    iframe[title*="qutwin_training_studio"] {display:block;border:0;}
    </style>'''.replace('#fcfaf4', background), unsafe_allow_html=True)
    event = _studio(model=model, key='studio_'+athlete_id, default=None)
    seen_key = 'studio_last_event_'+athlete_id
    if not isinstance(event, dict) or event.get('nonce') == st.session_state.get(seen_key): return
    if event.get('action') == 'theme' and event.get('theme') in ('dawn', 'dusk'):
        st.session_state[seen_key] = event.get('nonce')
        st.session_state[theme_key] = event['theme']
        st.rerun()
    action = resolve_action(event, [u['id'] for u in uploads])
    if not action: return
    st.session_state[seen_key] = event['nonce']
    if action['upload_id'] is not None:
        st.session_state['studio_target_upload'] = str(action['upload_id'])
    if action['action'] == 'events':
        from prediction.event_context import EVENTS
        st.session_state.setdefault('simple_upload_'+athlete_id+'_events', [e for e in model['events'] if e in EVENTS])
    if action['page']: st.session_state.current_page = action['page']
    st.rerun()
