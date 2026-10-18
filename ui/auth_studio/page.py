"""Streamlit entry point. The component owns its camera between interactions."""
from pathlib import Path
from time import monotonic
import streamlit as st
import streamlit.components.v1 as components

FRONTEND = Path(__file__).with_name('frontend')
_component = components.declare_component('qutwin_auth_studio', path=str(FRONTEND))

_CSS = '''<style>
header[data-testid="stHeader"], [data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"], [data-testid="stToolbar"],
footer, #MainMenu {display:none!important}
[data-testid="stAppViewContainer"], [data-testid="stMain"] {background:#163c31!important}
[data-testid="stMainBlockContainer"],.main .block-container {
 padding:0!important;margin:0!important;max-width:100%!important;width:100%!important;
}
[data-testid="stMainBlockContainer"]>div {gap:0!important}
.st-key-qutwin_auth_mount {margin:0!important;padding:0!important;gap:0!important;}
.st-key-qutwin_auth_mount iframe {display:block;border:0;width:100%!important;height:100dvh!important;min-height:640px;}
.st-key-qutwin_auth_mount [data-testid="stElementContainer"] {margin:0!important;}
@media(max-width:600px){.st-key-qutwin_auth_mount iframe{min-height:100dvh}}
</style>'''


def render_auth(initial_page='Login'):
    st.html(_CSS)
    key = '_qutwin_auth_response'
    response = st.session_state.get(key)
    with st.container(key='qutwin_auth_mount'):
        event = _component(initial_page=initial_page, response=response,
                           key='qutwin_auth_component', default=None)
    if not isinstance(event, dict) or event.get('action') == 'ack':
        return
    nonce = event.get('nonce')
    if not isinstance(nonce, str) or len(nonce) > 100:
        return
    if nonce == st.session_state.get('_qutwin_auth_last_event'):
        return
    st.session_state['_qutwin_auth_last_event'] = nonce
    from services.cinematic_auth import authenticate, register_account, AuthInputError
    action = event.get('action')
    result = {'nonce':nonce, 'ok':False, 'message':'Please try again.'}
    try:
        if action == 'login':
            attempts = st.session_state.get('_qutwin_login_failures', [])
            now = monotonic()
            attempts = [t for t in attempts if now-t < 60]
            if len(attempts) >= 8:
                raise AuthInputError('Please wait a minute before trying again.')
            user = authenticate(event.get('data'))
            if user:
                from authentication.session import login_user
                st.session_state['_qutwin_login_failures'] = []
                st.session_state.pop(key, None)
                st.session_state.current_page = 'Athlete Home' if user['role']=='Athlete' else 'Digital Twin Dashboard'
                st.session_state.coach_display_name = user['name']
                theme = event.get('theme', 'dawn')
                if theme not in ('dawn', 'dusk'): theme = 'dawn'
                st.session_state['studio_theme_'+user['user_id']] = theme
                login_user(user['role'], user['user_id'])
                st.rerun()
            else:
                st.session_state['_qutwin_login_failures'] = attempts+[now]
                result['message'] = 'The account type, User ID/email or password is incorrect.'
        elif action == 'signup':
            user = register_account(event.get('data'))
            result.update(ok=True, message='Your account has been saved.', user_id=user['user_id'], role=user['role'])
        elif action == 'reset':
            # Matches the actual backend: no email provider is configured.
            result['message'] = 'Password reset email is not configured in this project. Please contact your QUTwin administrator.'
        else:
            return
    except AuthInputError as exc:
        result['message'] = str(exc)
    except Exception:
        # Do not leak SQL, connection configuration, or personal data to the UI.
        result['message'] = 'We could not connect to the account database or save these details. Check the project database setup and try again.'
    st.session_state[key] = result
    st.rerun()

