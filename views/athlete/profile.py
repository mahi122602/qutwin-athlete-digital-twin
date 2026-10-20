"""Photographic athlete profile, connected to the existing QUTwin repositories."""
from pathlib import Path
import base64
import logging
import uuid

import streamlit as st
import streamlit.components.v1 as components

from database.athlete_repository import get_athlete_profile, update_athlete_profile
from database.twin_repository import get_athlete_twin_history
from ui.athlete_profile_model import build_profile_model, validate_changes
from services.profile_portrait import prepare_portrait, position_portrait, clean_layout, portrait_info, PortraitProcessingError

_FRONTEND = Path(__file__).resolve().parents[2] / "ui" / "athlete_profile_frontend"
_profile_studio = components.declare_component("qutwin_athlete_profile_photo", path=str(_FRONTEND))
_log = logging.getLogger(__name__)
_ROUTES = [("Studio", "Athlete Home"), ("Add activity", "Upload Garmin Data"),
           ("Predictions", "Predictions & Coach Recommendations"), ("Forecasting", "Forecasting"),
           ("Journal", "Digital Twin History"), ("Coach", "Requests")]


def _go(page):
    st.session_state.current_page = page


def _theme(key):
    st.session_state[key] = "dawn" if st.session_state.get(key, "dawn") == "dusk" else "dusk"


def _sign_out():
    from authentication.session import logout_user
    logout_user()


def _navigation(model, theme_key):
    photo_css = ("background-image:url('" + model["avatar"] + "')!important;background-size:cover!important;background-position:center!important;"
                 if model.get("avatar") else "")
    st.html('''<style>
html body [data-testid="stMainBlockContainer"],html body .block-container{max-width:none!important;padding:0!important;}
html body .st-key-studio_suite_nav,html body header[data-testid="stHeader"],html body [data-testid="stToolbar"],html body [data-testid="stDecoration"]{display:none!important;}
html body .st-key-athlete_page_content{gap:0!important;}
iframe[title*="qutwin_athlete_profile_photo"]{display:block;border:0;width:100%;}
html body .st-key-pp_nav{position:fixed!important;top:0!important;left:0!important;right:0!important;width:100vw!important;z-index:10020!important;
background:#17352ef5!important;color:#f6f4e9!important;border:0!important;border-bottom:1px solid #b9c5af35!important;
box-sizing:border-box!important;border-radius:0!important;margin:0!important;padding:7px 2.1vw!important;backdrop-filter:blur(16px);}
.st-key-pp_nav [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:8px!important;align-items:center!important;}
.st-key-pp_nav [data-testid="stColumn"]{min-width:0!important;}
.st-key-pp_nav [data-testid="stButton"] button,.st-key-pp_nav [data-testid="stPopoverButton"]{border:0!important;border-radius:7px!important;background:transparent!important;color:#f6f4e9!important;box-shadow:none!important;min-height:40px!important;padding:6px 8px!important;}
.st-key-pp_nav button p{font:400 15px Arial,sans-serif!important;color:#f6f4e9!important;white-space:nowrap!important;}
.st-key-pp_nav button:hover{background:#ffffff12!important;transform:none!important;}
.st-key-pp_nav button:focus-visible{outline:2px solid #f1c397!important;outline-offset:2px!important;}
.pp-brand{font:500 29px Georgia,serif;white-space:nowrap;letter-spacing:-.5px;color:#f6f4e9;padding:0 2px;}
.pp-brand span{font-size:24px;margin-right:7px;color:#e6e8d5;}
.st-key-pp_nav .st-key-pp_theme [data-testid="stButton"] button{border:1px solid #c6d0bd77!important;border-radius:24px!important;}
.st-key-pp_theme button p{font-size:13px!important;}
.st-key-pp_account [data-testid="stPopoverButton"]{border:1px solid #c6d0bd99!important;border-radius:50%!important;width:39px!important;height:39px!important;min-height:39px!important;padding:0!important;PHOTO_CSS}
.st-key-pp_account [data-testid="stPopoverButton"]>svg{display:none!important;}
.st-key-pp_account [data-testid="stPopoverButton"] p{AVATAR_TEXT}
.st-key-pp_menu{display:none!important;}
html body .st-key-pp_privacy{max-width:1440px!important;margin:0 auto!important;padding:16px 4vw 32px!important;}
html body .st-key-pp_privacy hr{display:none!important;}
@media(max-width:1050px){
 .st-key-pp_nav [data-testid="stColumn"]:has([class*="st-key-pp_link_"]){display:none!important;}
 .st-key-pp_nav [data-testid="stColumn"]{flex:0 0 auto!important;width:auto!important;}
 .st-key-pp_nav [data-testid="stColumn"]:has(.pp-brand){flex:1 1 auto!important;}
 .st-key-pp_menu{display:block!important;}
 .st-key-pp_nav{padding:7px 16px!important;}
 .st-key-pp_nav [data-testid="stHorizontalBlock"]{gap:10px!important;}
 .pp-brand{font-size:24px;}
 .st-key-pp_theme{min-width:76px!important;}
 .st-key-pp_account{min-width:39px!important;}
 .st-key-pp_menu{min-width:36px!important;}
}
</style>'''.replace("PHOTO_CSS", photo_css).replace("AVATAR_TEXT", "opacity:0!important;" if photo_css else "font-size:12px!important;"))
    with st.container(key="pp_nav"):
        cols = st.columns([1.9, .85, 1.25, 1.2, 1.15, .85, .75, 1.05, .45, .45], gap="small", vertical_alignment="center")
        cols[0].html('<div class="pp-brand"><span>◇</span>QUTwin</div>')
        for index, (label, route) in enumerate(_ROUTES, 1):
            with cols[index].container(key="pp_link_" + str(index)):
                st.button(label, key="pp_go_" + str(index), use_container_width=True, on_click=_go, args=(route,))
        with cols[7].container(key="pp_theme"):
            st.button("☾ Dusk" if model["theme"] == "dusk" else "☀ Dawn", key="pp_theme_switch", use_container_width=True,
                      help="Switch the shared studio theme", on_click=_theme, args=(theme_key,))
        with cols[8].container(key="pp_account"):
            with st.popover(model["initials"], help="Your account", use_container_width=True):
                st.button("My profile", key="pp_account_profile", on_click=_go, args=("Profile",), use_container_width=True)
                st.button("Notifications", key="pp_account_notifications", on_click=_go, args=("Notifications",), use_container_width=True)
                st.button("Settings", key="pp_account_settings", on_click=_go, args=("Settings",), use_container_width=True)
                st.button("Sign out", key="pp_sign_out", on_click=_sign_out, use_container_width=True)
        with cols[9].container(key="pp_menu"):
            with st.popover("☰", help="Open navigation", use_container_width=True):
                for index, (label, route) in enumerate(_ROUTES):
                    st.button(label, key="pp_mobile_" + str(index), on_click=_go, args=(route,), use_container_width=True)


def athlete_profile():
    if not st.session_state.get("logged_in") or st.session_state.get("role") != "Athlete" or not st.session_state.get("user_id"):
        st.error("Sign in as an athlete to open your profile.")
        return
    athlete_id = str(st.session_state.user_id)
    try:
        profile = get_athlete_profile(athlete_id)
    except Exception:
        _log.exception("Athlete profile load failed")
        st.error("Your profile could not be loaded. Refresh to try again.")
        return
    if profile is None:
        st.error("Athlete profile not found.")
        return
    try:
        history = get_athlete_twin_history(athlete_id)
        history_available = True
    except Exception:
        history, history_available = None, False
    theme_key = "studio_theme_" + athlete_id
    notice_key = "profile_studio_notice_" + athlete_id
    seen_key = "profile_studio_event_" + athlete_id
    preview_key = "profile_portrait_preview_" + athlete_id
    ready_photo = None
    photo_warning = None
    raw_photo = profile.get("profile_photo")
    if raw_photo:
        try:
            ready_photo = prepare_portrait(bytes(raw_photo))
        except PortraitProcessingError as exc:
            _log.exception("Saved portrait processing failed")
            photo_warning = str(exc)
        except Exception:
            _log.exception("Saved portrait could not be opened")
            photo_warning = "Your saved photo could not be prepared. Open Edit profile to upload another photo. The app terminal has the error."
    displayed = dict(profile)
    if ready_photo is not None:
        displayed["profile_photo"] = ready_photo
    model = build_profile_model(displayed, athlete_id, history, history_available,
                                st.session_state.get(theme_key, "dawn"), st.session_state.get(notice_key))
    model["photo_warning"] = photo_warning
    preview = st.session_state.get(preview_key)
    if preview:
        model["photo_preview"] = {"nonce": preview["nonce"], "token": preview["token"],
            "uri": "data:image/png;base64," + base64.b64encode(preview["data"]).decode("ascii"),
            "layout": portrait_info(preview["data"])["layout"]}
    _navigation(model, theme_key)
    event = _profile_studio(model=model, key="athlete_profile_photo_" + athlete_id, default=None)
    if isinstance(event, dict):
        nonce = event.get("nonce")
        fresh = isinstance(nonce, str) and 0 < len(nonce) <= 100 and nonce != st.session_state.get(seen_key)
        if fresh:
            st.session_state[seen_key] = nonce
            action = event.get("action")
            if action == "theme" and event.get("theme") in ("dawn", "dusk"):
                st.session_state[theme_key] = event["theme"]
                st.rerun()
            elif action == "upload":
                st.session_state.current_page = "Upload Garmin Data"
                st.rerun()
            elif action == "prepare_photo":
                try:
                    if event.get("source") == "saved":
                        if not raw_photo:
                            raise ValueError("Choose a photo first.")
                        uploaded = bytes(raw_photo)
                    else:
                        fields = dict(model["fields"], photo=event.get("photo"))
                        uploaded = validate_changes(fields)["profile_photo"]
                        if uploaded is None:
                            raise ValueError("Choose a photo first.")
                    data = prepare_portrait(uploaded)
                    st.session_state[preview_key] = {"data": data, "nonce": nonce, "token": uuid.uuid4().hex}
                    st.session_state.pop(notice_key, None)
                except Exception as exc:
                    _log.exception("Portrait preview failed")
                    message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "Your photo could not be processed. Choose another image or a transparent PNG."
                    st.session_state[notice_key] = dict(kind="error", nonce=nonce, message=message)
                st.rerun()
            elif action == "save":
                try:
                    payload = event.get("changes")
                    changes = validate_changes(payload)
                    layout = clean_layout(payload.get("photo_layout"))
                    token = payload.get("photo_token")
                    if token is not None:
                        preview = st.session_state.get(preview_key)
                        if not preview or token != preview["token"]:
                            raise ValueError("Choose your photo again before saving.")
                        changes["profile_photo"] = position_portrait(preview["data"], layout)
                    elif changes["profile_photo"] is not None:
                        changes["profile_photo"] = position_portrait(changes["profile_photo"], layout)
                    elif ready_photo is not None:
                        changes["profile_photo"] = position_portrait(ready_photo, layout)
                except Exception as exc:
                    _log.exception("Profile validation or portrait placement failed")
                    message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "Your photo could not be prepared for saving. Your draft is still here. The app terminal has the error."
                    st.session_state[notice_key] = dict(kind="error", message=message, nonce=nonce)
                else:
                    try:
                        update_athlete_profile(athlete_id=athlete_id, **changes)
                    except Exception:
                        _log.exception("Athlete profile save failed")
                        st.session_state[notice_key] = dict(kind="error", nonce=nonce,
                            message="Your profile could not be saved. Your edits are still here; please try again.")
                    else:
                        if changes["profile_photo"] is not None:
                            st.session_state.profile_photo = changes["profile_photo"]
                        st.session_state.pop(preview_key, None)
                        st.session_state[notice_key] = dict(kind="success", nonce=nonce, message="Your profile has been saved.")
                st.rerun()
    from views.athlete.privacy_controls import render_delete_account
    with st.container(key="pp_privacy"):
        render_delete_account()
