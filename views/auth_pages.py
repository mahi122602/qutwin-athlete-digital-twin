from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import streamlit as st

from authentication.session import login_user
from database.athlete_repository import login_athlete, register_athlete
from database.coach_repository import login_coach, register_coach


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Your project folder is named "assests" (double s), not "assets".
# Keep the assets fallback so the code still works if you rename it later.
ASSETS_ROOT = (
    PROJECT_ROOT / "assests"
    if (PROJECT_ROOT / "assests").exists()
    else PROJECT_ROOT / "assets"
)

VIDEO_PATH = ASSETS_ROOT / "videos" / "cloud_morning.mp4"
LOGO_PATH = ASSETS_ROOT / "logo.png"


def _data_uri(path: Path) -> str | None:
    try:
        if not path.exists():
            return None
        mime, _ = mimetypes.guess_type(str(path))
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime or 'application/octet-stream'};base64,{encoded}"
    except OSError:
        return None


def _apply_auth_ui() -> None:
    video_uri = _data_uri(VIDEO_PATH)

    video_html = (
        f"""
        <video class="auth-video" autoplay muted loop playsinline>
            <source src="{video_uri}" type="video/mp4">
        </video>
        """
        if video_uri
        else '<div class="auth-fallback"></div>'
    )

    st.html(
        f"""
        {video_html}
        <div class="auth-overlay"></div>

        <style>
        #MainMenu,
        footer,
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        section[data-testid="stSidebar"],
        [data-testid="collapsedControl"] {{
            display: none !important;
        }}

        html, body,
        [data-testid="stAppViewContainer"],
        .stApp, .main {{
            width: 100% !important;
            height: 100dvh !important;
            min-height: 100dvh !important;
            max-height: 100dvh !important;
            margin: 0 !important;
            overflow: hidden !important;
        }}

        .auth-video,
        .auth-fallback {{
            position: fixed;
            inset: 0;
            width: 100vw;
            height: 100dvh;
            z-index: 0;
        }}

        .auth-video {{
            object-fit: cover;
            object-position: center;
        }}

        .auth-fallback {{
            background: #9edff0;
        }}

        .auth-overlay {{
            position: fixed;
            inset: 0;
            z-index: 1;
            background: rgba(3, 20, 32, 0.22);
            pointer-events: none;
        }}

        .main {{
            position: relative;
            z-index: 2;
        }}

        .main .block-container {{
            width: 100% !important;
            max-width: 100% !important;
            height: 100dvh !important;
            min-height: 100dvh !important;
            max-height: 100dvh !important;
            padding: 12px !important;
            margin: 0 !important;
            overflow: hidden !important;
        }}

        .main .block-container > div[data-testid="stVerticalBlock"] {{
            height: 100% !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            width: 100% !important;
            max-width: 430px !important;
            margin: 0 auto !important;
            border: none !important;
            border-radius: 22px !important;
            background: #ffffff !important;
            box-shadow: 0 24px 70px rgba(0,0,0,0.28) !important;
            overflow: hidden !important;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"]
        > div[data-testid="stVerticalBlock"] {{
            padding: 22px 28px 20px !important;
            gap: 0.45rem !important;
        }}

        .auth-brand {{
            text-align: center;
            margin-bottom: 8px;
        }}

        .auth-logo {{
            width: 52px;
            height: 52px;
            object-fit: contain;
            border-radius: 12px;
            margin-bottom: 5px;
        }}

        .auth-title {{
            margin: 0;
            color: #178fae;
            font-size: 29px;
            font-weight: 850;
        }}

        .auth-subtitle {{
            margin: 4px 0 0;
            color: #68828b;
            font-size: 11px;
        }}

        label {{
            color: #355864 !important;
            font-size: 11px !important;
            font-weight: 700 !important;
        }}

        div[data-baseweb="select"] > div,
        div[data-testid="stTextInput"] > div > div,
        div[data-testid="stNumberInput"] input {{
            min-height: 38px !important;
            border-radius: 9px !important;
            border: 1px solid #d8e4e8 !important;
            background: #f8fbfc !important;
            box-shadow: none !important;
        }}

        input {{
            color: #294c58 !important;
            background: transparent !important;
            font-size: 12px !important;
        }}

        .stButton > button {{
            width: 100%;
            min-height: 38px;
            border: none !important;
            border-radius: 9px !important;
            color: white !important;
            background: #36abc9 !important;
            font-size: 12px !important;
            font-weight: 750 !important;
        }}

        div[data-testid="stAlert"] {{
            font-size: 10px !important;
            padding: 6px 8px !important;
            border-radius: 8px !important;
        }}

        @media (max-height: 750px) {{
            div[data-testid="stVerticalBlockBorderWrapper"]
            > div[data-testid="stVerticalBlock"] {{
                padding: 12px 24px 11px !important;
                gap: 0.25rem !important;
            }}

            .auth-logo {{
                width: 40px;
                height: 40px;
            }}

            .auth-title {{
                font-size: 24px;
            }}

            div[data-baseweb="select"] > div,
            div[data-testid="stTextInput"] > div > div,
            div[data-testid="stNumberInput"] input,
            .stButton > button {{
                min-height: 32px !important;
            }}
        }}
        </style>
        """
    )


def _brand() -> None:
    logo_uri = _data_uri(LOGO_PATH)
    logo = f'<img class="auth-logo" src="{logo_uri}" alt="QUTwin logo">' if logo_uri else ""

    st.html(
        f"""
        <div class="auth-brand">
            {logo}
            <h1 class="auth-title">QUTwin</h1>
            <p class="auth-subtitle">Athlete Digital Twin Performance Intelligence</p>
        </div>
        """
    )


def login_page() -> None:
    _apply_auth_ui()

    left, centre, right = st.columns([1, 0.72, 1])

    with centre:
        with st.container(border=True):
            _brand()

            role = st.selectbox("Role", ["Athlete", "Coach"], key="login_role")

            user_id = st.text_input(
                "User ID",
                placeholder="Enter your ID",
                key=f"login_id_{role.lower()}",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key=f"login_password_{role.lower()}",
            )

            if st.button("Login", use_container_width=True, key=f"login_{role.lower()}"):
                clean_id = user_id.strip()

                if not clean_id or not password:
                    st.error("Enter your ID and password.")
                else:
                    success = (
                        login_athlete(clean_id, password)
                        if role == "Athlete"
                        else login_coach(clean_id, password)
                    )

                    if success:
                        login_user(role, clean_id)
                        st.session_state.current_page = (
                            "Athlete Home"
                            if role == "Athlete"
                            else "Digital Twin Dashboard"
                        )
                        st.rerun()
                    else:
                        st.error("Invalid login details.")

            c1, c2 = st.columns(2)

            with c1:
                if st.button("Create account", use_container_width=True):
                    st.session_state.auth_page = "Signup"
                    st.rerun()

            with c2:
                if st.button("Forgot password?", use_container_width=True):
                    st.session_state.auth_page = "Forgot Password"
                    st.rerun()


def signup_page() -> None:
    _apply_auth_ui()

    left, centre, right = st.columns([1, 0.85, 1])

    with centre:
        with st.container(border=True):
            _brand()

            role = st.selectbox("Create account as", ["Athlete", "Coach"], key="signup_role")
            user_id = st.text_input("User ID", key=f"signup_id_{role.lower()}")
            name = st.text_input("Full name", key=f"signup_name_{role.lower()}")
            password = st.text_input("Password", type="password", key=f"signup_password_{role.lower()}")
            confirm = st.text_input("Confirm password", type="password", key=f"signup_confirm_{role.lower()}")

            athlete_values = None

            if role == "Athlete":
                a, b = st.columns(2)

                with a:
                    age = st.number_input("Age", 10, 80, 22)
                    weight = st.number_input("Weight (kg)", 30.0, 250.0, 70.0)

                with b:
                    height = st.number_input("Height (cm)", 100.0, 250.0, 170.0)
                    previous_injury = st.number_input("Previous injuries", 0, 30, 0)

                athlete_values = age, height, weight, previous_injury

            if st.button(f"Create {role} account", use_container_width=True):
                if not user_id.strip() or not name.strip() or not password:
                    st.error("Complete all required fields.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                else:
                    if role == "Athlete":
                        age, height, weight, previous_injury = athlete_values
                        register_athlete(
                            user_id.strip(),
                            name.strip(),
                            password,
                            age,
                            height,
                            weight,
                            previous_injury,
                        )
                    else:
                        register_coach(user_id.strip(), name.strip(), password)

                    st.session_state.auth_page = "Login"
                    st.rerun()

            if st.button("Back to login", use_container_width=True):
                st.session_state.auth_page = "Login"
                st.rerun()


def forgot_password_page() -> None:
    _apply_auth_ui()

    left, centre, right = st.columns([1, 0.72, 1])

    with centre:
        with st.container(border=True):
            _brand()

            role = st.selectbox("Account type", ["Athlete", "Coach"], key="reset_role")
            user_id = st.text_input("User ID", key=f"reset_id_{role.lower()}")
            email = st.text_input("Registered email", key=f"reset_email_{role.lower()}")

            if st.button("Send reset request", use_container_width=True):
                if not user_id.strip() or not email.strip():
                    st.error("Enter your ID and email.")
                else:
                    st.info("Password reset email still needs to be connected.")

            if st.button("Back to login", use_container_width=True):
                st.session_state.auth_page = "Login"
                st.rerun()