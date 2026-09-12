from __future__ import annotations
from utils.assets import cache_file_result
import base64
import mimetypes
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ASSETS_ROOT = (
    PROJECT_ROOT / "assests"
    if (PROJECT_ROOT / "assests").exists()
    else PROJECT_ROOT / "assets"
)

VIDEO_PATH = (
    ASSETS_ROOT
    / "videos"
    / "cloud_morning.mp4"
)

LOGO_PATH = (
    ASSETS_ROOT
    / "logo.png"
)

@cache_file_result
def _data_uri(path: Path) -> str | None:
    try:
        if not path.exists():
            return None

        mime, _ = mimetypes.guess_type(
            str(path)
        )

        encoded = base64.b64encode(
            path.read_bytes()
        ).decode("utf-8")

        return (
            f"data:"
            f"{mime or 'application/octet-stream'};"
            f"base64,{encoded}"
        )

    except OSError:
        return None

def _apply_auth_ui() -> None:

    video_uri = _data_uri(
        VIDEO_PATH
    )

    video_html = (
        f"""
        <video
            class="auth-video"
            autoplay
            muted
            loop
            playsinline
        >
            <source
                src="{video_uri}"
                type="video/mp4"
            >
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

        /* ==================================================
           HIDE STREAMLIT DEFAULT UI
        ================================================== */

        #MainMenu,
        footer,
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        section[data-testid="stSidebar"],
        [data-testid="collapsedControl"] {{
            display: none !important;
        }}


        /* ==================================================
           FULL SCREEN PAGE
        ================================================== */

        html,
        body,
        [data-testid="stAppViewContainer"],
        .stApp,
        .main {{
            width: 100% !important;
            min-height: 100dvh !important;
            margin: 0 !important;
            padding: 0 !important;
        }}

        html,
        body {{
            overflow: hidden !important;
        }}


        /* ==================================================
           EXISTING VIDEO BACKGROUND
        ================================================== */

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
            background:
                linear-gradient(
                    135deg,
                    #06101d,
                    #0b2b44
                );
        }}


        /* ==================================================
           BACKGROUND OVERLAY

           Keeps the original video visible while making
           foreground text easier to read.
        ================================================== */

        .auth-overlay {{
            position: fixed;
            inset: 0;

            z-index: 1;

            background:
                rgba(
                    1,
                    8,
                    18,
                    0.18
                );

            pointer-events: none;
        }}


        /* ==================================================
           STREAMLIT CONTENT
        ================================================== */

        .main {{
            position: relative;
            z-index: 2;
        }}

        .main .block-container {{
            width: 100% !important;
            max-width: 100% !important;

            min-height: 100dvh !important;

            margin: 0 !important;

            padding:
                28px
                20px
                28px
                20px
                !important;

            overflow-y: auto !important;
            overflow-x: hidden !important;
        }}

        .main
        .block-container
        > div[data-testid="stVerticalBlock"] {{
            min-height:
                calc(
                    100dvh - 56px
                );

            display: flex !important;
            flex-direction: column !important;

            justify-content: center !important;
        }}


        /* ==================================================
           MATTE / GLASS AUTH CARDS

           These are keyed Streamlit containers, which is
           more reliable than styling generic border wrappers.
        ================================================== */

        .st-key-login_card,
        .st-key-signup_card,
        .st-key-reset_card {{
            position: relative !important;
            isolation: isolate !important;

            width: 100% !important;
            max-width: 560px !important;

            margin:
                0
                auto
                !important;

            padding:
                38px
                40px
                34px
                40px
                !important;

            border-radius:
                28px
                !important;

            border:
                1px
                solid
                rgba(
                    207,
                    228,
                    250,
                    0.28
                )
                !important;

            background:
                linear-gradient(
                    145deg,
                    rgba(
                        16,
                        35,
                        56,
                        0.76
                    ),
                    rgba(
                        5,
                        17,
                        31,
                        0.82
                    )
                )
                !important;

            backdrop-filter:
                blur(22px)
                saturate(135%)
                !important;

            -webkit-backdrop-filter:
                blur(22px)
                saturate(135%)
                !important;

            box-shadow:
                0
                28px
                75px
                rgba(
                    0,
                    0,
                    0,
                    0.50
                ),
                inset
                0
                1px
                0
                rgba(
                    255,
                    255,
                    255,
                    0.10
                )
                !important;

            overflow: hidden !important;
        }}


        /* ==================================================
           GLASS HIGHLIGHT
        ================================================== */

        .st-key-login_card::before,
        .st-key-signup_card::before,
        .st-key-reset_card::before {{
            content: "";

            position: absolute;
            inset: 0;

            border-radius:
                28px;

            background:
                linear-gradient(
                    135deg,
                    rgba(
                        255,
                        255,
                        255,
                        0.075
                    ),
                    transparent
                    38%
                );

            pointer-events: none;

            z-index: 0;
        }}

        .st-key-login_card > *,
        .st-key-signup_card > *,
        .st-key-reset_card > * {{
            position: relative;
            z-index: 1;
        }}


        /* ==================================================
           INTERNAL CARD SPACING
        ================================================== */

        .st-key-login_card
        div[data-testid="stVerticalBlock"],

        .st-key-signup_card
        div[data-testid="stVerticalBlock"],

        .st-key-reset_card
        div[data-testid="stVerticalBlock"] {{
            gap:
                0.70rem
                !important;
        }}


        /* ==================================================
           BRAND
        ================================================== */

        .auth-brand {{
            text-align: center;

            margin-bottom:
                16px;
        }}

        .auth-logo {{
            width:
                72px;

            height:
                72px;

            object-fit:
                contain;

            padding:
                6px;

            margin-bottom:
                10px;

            border-radius:
                18px;

            background:
                rgba(
                    255,
                    255,
                    255,
                    0.90
                );

            box-shadow:
                0
                10px
                28px
                rgba(
                    0,
                    0,
                    0,
                    0.30
                );
        }}

        .auth-title {{
            margin:
                0;

            color:
                #ffffff;

            font-size:
                42px;

            font-weight:
                850;

            letter-spacing:
                0.4px;

            line-height:
                1.1;
        }}

        .auth-highlight {{
            color:
                #31bfe4;
        }}

        .auth-subtitle {{
            margin:
                9px
                auto
                0;

            max-width:
                420px;

            color:
                #c6d7e7;

            font-size:
                16px;

            font-weight:
                500;

            line-height:
                1.55;
        }}

        .auth-page-heading {{
            text-align:
                center;

            color:
                #ffffff;

            font-size:
                27px;

            font-weight:
                750;

            line-height:
                1.2;

            margin:
                5px
                0
                18px;
        }}


        /* ==================================================
           LABELS
        ================================================== */

        label,
        div[data-testid="stWidgetLabel"] p {{
            color:
                #f1f6fc
                !important;

            font-size:
                16px
                !important;

            font-weight:
                650
                !important;

            letter-spacing:
                0.1px
                !important;
        }}


        /* ==================================================
           TEXT INPUTS / PASSWORD INPUTS
        ================================================== */

        div[data-testid="stTextInput"]
        > div
        > div {{
            min-height:
                56px
                !important;

            border:
                1px
                solid
                rgba(
                    174,
                    207,
                    237,
                    0.30
                )
                !important;

            border-radius:
                15px
                !important;

            background:
                rgba(
                    3,
                    14,
                    27,
                    0.68
                )
                !important;

            box-shadow:
                inset
                0
                1px
                0
                rgba(
                    255,
                    255,
                    255,
                    0.035
                )
                !important;

            transition:
                border-color
                0.2s
                ease,
                box-shadow
                0.2s
                ease,
                background
                0.2s
                ease
                !important;
        }}

        div[data-testid="stTextInput"]
        > div
        > div:focus-within {{
            border-color:
                #3cc7e8
                !important;

            background:
                rgba(
                    3,
                    15,
                    29,
                    0.86
                )
                !important;

            box-shadow:
                0
                0
                0
                3px
                rgba(
                    60,
                    199,
                    232,
                    0.13
                )
                !important;
        }}


        /* ==================================================
           INPUT TEXT
        ================================================== */

        input {{
            color:
                #ffffff
                !important;

            background:
                transparent
                !important;

            font-size:
                16px
                !important;

            font-weight:
                500
                !important;

            caret-color:
                #38c1e3
                !important;
        }}

        input::placeholder {{
            color:
                #91a7ba
                !important;

            opacity:
                1
                !important;

            font-size:
                15px
                !important;
        }}


        /* ==================================================
           PASSWORD EYE
        ================================================== */

        div[data-testid="stTextInput"]
        button {{
            color:
                #c5d6e3
                !important;
        }}


        /* ==================================================
           ROLE DROPDOWN
        ================================================== */

        div[data-baseweb="select"]
        > div {{
            min-height:
                56px
                !important;

            border:
                1px
                solid
                rgba(
                    174,
                    207,
                    237,
                    0.30
                )
                !important;

            border-radius:
                15px
                !important;

            background:
                rgba(
                    3,
                    14,
                    27,
                    0.68
                )
                !important;

            box-shadow:
                none
                !important;
        }}

        div[data-baseweb="select"]
        > div:hover {{
            border-color:
                rgba(
                    60,
                    199,
                    232,
                    0.70
                )
                !important;
        }}

        div[data-baseweb="select"]
        span {{
            color:
                #ffffff
                !important;

            font-size:
                16px
                !important;

            font-weight:
                550
                !important;
        }}

        div[data-baseweb="select"]
        svg {{
            fill:
                #dceaf5
                !important;
        }}


        /* ==================================================
           DROPDOWN MENU
        ================================================== */

        ul[role="listbox"] {{
            background:
                #10263a
                !important;

            border:
                1px
                solid
                rgba(
                    255,
                    255,
                    255,
                    0.12
                )
                !important;

            border-radius:
                13px
                !important;
        }}

        ul[role="listbox"] li {{
            color:
                #f2f7fc
                !important;

            font-size:
                16px
                !important;

            font-weight:
                500
                !important;
        }}


        /* ==================================================
           NUMBER INPUTS
        ================================================== */

        div[data-testid="stNumberInput"]
        > div
        > div {{
            min-height:
                54px
                !important;

            background:
                rgba(
                    3,
                    14,
                    27,
                    0.68
                )
                !important;

            border:
                1px
                solid
                rgba(
                    174,
                    207,
                    237,
                    0.30
                )
                !important;

            border-radius:
                15px
                !important;
        }}

        div[data-testid="stNumberInput"]
        input {{
            color:
                #ffffff
                !important;

            font-size:
                16px
                !important;
        }}


        /* ==================================================
           BUTTONS
        ================================================== */

        .stButton
        > button {{
            width:
                100%
                !important;

            min-height:
                54px
                !important;

            border-radius:
                14px
                !important;

            border:
                1px
                solid
                rgba(
                    68,
                    195,
                    229,
                    0.50
                )
                !important;

            background:
                linear-gradient(
                    90deg,
                    #1489af,
                    #2db8d7
                )
                !important;

            color:
                #ffffff
                !important;

            font-size:
                16px
                !important;

            font-weight:
                750
                !important;

            letter-spacing:
                0.15px
                !important;

            box-shadow:
                0
                9px
                24px
                rgba(
                    18,
                    148,
                    185,
                    0.24
                )
                !important;

            transition:
                transform
                0.18s
                ease,
                filter
                0.18s
                ease,
                box-shadow
                0.18s
                ease
                !important;
        }}

        .stButton
        > button:hover {{
            transform:
                translateY(-1px)
                !important;

            filter:
                brightness(1.08)
                !important;

            box-shadow:
                0
                12px
                28px
                rgba(
                    17,
                    164,
                    205,
                    0.32
                )
                !important;

            border-color:
                #70d9f0
                !important;
        }}

        .stButton
        > button:focus {{
            color:
                #ffffff
                !important;

            border-color:
                #6dd7ee
                !important;
        }}


        /* ==================================================
           OR DIVIDER
        ================================================== */

        .auth-divider {{
            display:
                flex;

            align-items:
                center;

            gap:
                14px;

            margin:
                10px
                0
                4px;

            color:
                #a9bdcf;

            font-size:
                15px;

            font-weight:
                600;
        }}

        .auth-divider::before,
        .auth-divider::after {{
            content:
                "";

            flex:
                1;

            height:
                1px;

            background:
                rgba(
                    205,
                    224,
                    241,
                    0.22
                );
        }}


        /* ==================================================
           ALERTS
        ================================================== */

        div[data-testid="stAlert"] {{
            font-size:
                14px
                !important;

            border-radius:
                12px
                !important;

            padding:
                10px
                12px
                !important;
        }}


        /* ==================================================
           SIGNUP CARD CAN BE SLIGHTLY WIDER
        ================================================== */

        .st-key-signup_card {{
            max-width:
                620px
                !important;
        }}


        /* ==================================================
           SMALLER SCREEN HEIGHT
        ================================================== */

        @media (max-height: 850px) {{

            .main .block-container {{
                padding:
                    14px
                    !important;
            }}

            .main
            .block-container
            > div[data-testid="stVerticalBlock"] {{
                min-height:
                    calc(
                        100dvh - 28px
                    );
            }}

            .st-key-login_card,
            .st-key-signup_card,
            .st-key-reset_card {{
                padding:
                    24px
                    30px
                    22px
                    30px
                    !important;
            }}

            .auth-logo {{
                width:
                    54px;

                height:
                    54px;
            }}

            .auth-title {{
                font-size:
                    34px;
            }}

            .auth-subtitle {{
                font-size:
                    13px;
            }}

            .auth-page-heading {{
                font-size:
                    22px;

                margin-bottom:
                    12px;
            }}

            label,
            div[data-testid="stWidgetLabel"] p {{
                font-size:
                    14px
                    !important;
            }}

            input,
            div[data-baseweb="select"] span {{
                font-size:
                    14px
                    !important;
            }}

            div[data-baseweb="select"]
            > div,
            div[data-testid="stTextInput"]
            > div
            > div,
            .stButton
            > button {{
                min-height:
                    44px
                    !important;
            }}

            .stButton
            > button {{
                font-size:
                    14px
                    !important;
            }}
        }}


        /* ==================================================
           MOBILE
        ================================================== */

        @media (max-width: 650px) {{

            .main .block-container {{
                padding:
                    14px
                    !important;
            }}

            .st-key-login_card,
            .st-key-signup_card,
            .st-key-reset_card {{
                max-width:
                    96%
                    !important;

                padding:
                    26px
                    22px
                    24px
                    22px
                    !important;

                border-radius:
                    22px
                    !important;
            }}

            .auth-logo {{
                width:
                    58px;

                height:
                    58px;
            }}

            .auth-title {{
                font-size:
                    34px;
            }}

            .auth-subtitle {{
                font-size:
                    14px;
            }}

            .auth-page-heading {{
                font-size:
                    23px;
            }}
        }}

        </style>
        """
    )

def _brand(
    page_heading: str | None = None,
) -> None:

    logo_uri = _data_uri(
        LOGO_PATH
    )

    logo = (
        (
            f'<img '
            f'class="auth-logo" '
            f'src="{logo_uri}" '
            f'alt="QUTwin logo">'
        )
        if logo_uri
        else ""
    )

    heading_html = (
        (
            f'<div '
            f'class="auth-page-heading">'
            f'{page_heading}'
            f'</div>'
        )
        if page_heading
        else ""
    )

    st.html(
        f"""
        <div class="auth-brand">

            {logo}

            <h1 class="auth-title"><span class="auth-highlight">QU</span>Twin</h1>
            
            <p class="auth-subtitle">
                Athlete Digital Twin
                Performance Intelligence
            </p>

        </div>

        {heading_html}
        """
    )

def _auth_divider() -> None:

    st.html(
        """
        <div class="auth-divider">
            <span>or</span>
        </div>
        """
    )
