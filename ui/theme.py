import streamlit as st


def apply_theme():
    st.markdown(
        """
        <style>
        /* =========================================================
           GLOBAL APPLICATION RESET
        ========================================================= */

        :root {
            --bg-primary: #030712;
            --bg-secondary: #081120;
            --surface: rgba(15, 23, 42, 0.78);
            --surface-strong: rgba(10, 18, 34, 0.94);
            --surface-soft: rgba(22, 32, 52, 0.66);

            --border-soft: rgba(148, 163, 184, 0.16);
            --border-medium: rgba(148, 163, 184, 0.26);

            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;

            --accent-blue: #2563eb;
            --accent-cyan: #06b6d4;
            --accent-purple: #7c3aed;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;

            --radius-small: 12px;
            --radius-medium: 18px;
            --radius-large: 26px;

            --shadow-soft:
                0 18px 44px rgba(0, 0, 0, 0.22);

            --shadow-large:
                0 28px 80px rgba(0, 0, 0, 0.36);
        }


        html,
        body,
        [data-testid="stAppViewContainer"],
        .stApp {
            min-height: 100%;
            background:
                radial-gradient(
                    circle at 84% 12%,
                    rgba(14, 165, 233, 0.14),
                    transparent 23%
                ),
                radial-gradient(
                    circle at 9% 88%,
                    rgba(16, 185, 129, 0.10),
                    transparent 21%
                ),
                linear-gradient(
                    135deg,
                    #020617 0%,
                    #07101e 48%,
                    #02040a 100%
                ) !important;

            color: var(--text-primary);
        }


        #MainMenu,
        footer {
            visibility: hidden;
        }


        header[data-testid="stHeader"] {
            background: rgba(2, 6, 23, 0.68);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border-bottom: 1px solid rgba(148, 163, 184, 0.10);
        }


        /* =========================================================
           MAIN CONTENT LAYOUT
        ========================================================= */

        .main .block-container {
            position: relative;
            z-index: 2;

            width: 100%;
            max-width: 1500px;

            padding-top: 3rem;
            padding-bottom: 3rem;

            animation: pageEntrance 0.52s ease both;
        }


        @keyframes pageEntrance {
            from {
                opacity: 0;
                transform: translateY(16px);
                filter: blur(3px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
                filter: blur(0);
            }
        }


        h1,
        h2,
        h3,
        h4 {
            color: var(--text-primary);
            letter-spacing: -0.02em;
        }


        h1 {
            font-weight: 850;
        }


        p,
        span,
        label {
            color: var(--text-secondary);
        }


        /* =========================================================
           DASHBOARD BACKGROUND LIGHT EFFECTS
           Hidden automatically behind auth phone/video page because
           auth_pages.py applies its own fixed background.
        ========================================================= */

        .dashboard-orb {
            position: fixed;
            border-radius: 50%;
            pointer-events: none;
            z-index: 0;
            filter: blur(16px);
            opacity: 0.72;
        }


        .dashboard-orb-one {
            top: 8%;
            right: 7%;

            width: 260px;
            height: 260px;

            background:
                radial-gradient(
                    circle,
                    rgba(56, 189, 248, 0.26),
                    rgba(99, 102, 241, 0.03)
                );

            animation: orbitOne 8s ease-in-out infinite;
        }


        .dashboard-orb-two {
            bottom: 8%;
            left: 6%;

            width: 220px;
            height: 220px;

            background:
                radial-gradient(
                    circle,
                    rgba(16, 185, 129, 0.20),
                    rgba(14, 165, 233, 0.02)
                );

            animation: orbitTwo 10s ease-in-out infinite;
        }


        @keyframes orbitOne {
            0%,
            100% {
                transform: translateY(0) scale(1);
            }

            50% {
                transform: translateY(-30px) scale(1.08);
            }
        }


        @keyframes orbitTwo {
            0%,
            100% {
                transform: translate(0, 0);
            }

            50% {
                transform: translate(28px, 20px);
            }
        }


        /* =========================================================
           SIDEBAR — COACH ONLY
        ========================================================= */

        section[data-testid="stSidebar"] {
            background:
                linear-gradient(
                    180deg,
                    #061020 0%,
                    #0b1528 55%,
                    #101827 100%
                );

            border-right: 1px solid var(--border-soft);

            box-shadow:
                12px 0 38px rgba(0, 0, 0, 0.25);
        }


        section[data-testid="stSidebar"] > div {
            padding-top: 1.4rem;
        }


        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: var(--text-primary);
            font-weight: 800;
        }


        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label {
            color: var(--text-secondary);
        }


        section[data-testid="stSidebar"] hr {
            border-color: rgba(148, 163, 184, 0.15);
        }


        /* Coach sidebar radio navigation */

        section[data-testid="stSidebar"]
        div[role="radiogroup"] {
            gap: 0.35rem;
        }


        section[data-testid="stSidebar"]
        div[role="radiogroup"] label {
            min-height: 46px;

            padding: 0.72rem 0.82rem;
            margin-bottom: 0.35rem;

            border-radius: 13px;
            border: 1px solid transparent;

            background: transparent;

            transition:
                background 180ms ease,
                border-color 180ms ease,
                transform 180ms ease,
                box-shadow 180ms ease;
        }


        section[data-testid="stSidebar"]
        div[role="radiogroup"] label:hover {
            background: rgba(37, 99, 235, 0.15);
            border-color: rgba(96, 165, 250, 0.28);
            transform: translateX(3px);
        }


        section[data-testid="stSidebar"]
        div[role="radiogroup"] label:has(input:checked) {
            background:
                linear-gradient(
                    135deg,
                    rgba(37, 99, 235, 0.94),
                    rgba(124, 58, 237, 0.88)
                );

            border-color: rgba(255, 255, 255, 0.22);

            box-shadow:
                0 10px 26px rgba(37, 99, 235, 0.30);
        }


        /* =========================================================
           GENERIC CARDS
        ========================================================= */

        .hero-card,
        .section-card,
        .glass-card,
        .content-card {
            position: relative;

            background:
                linear-gradient(
                    150deg,
                    rgba(15, 23, 42, 0.82),
                    rgba(8, 16, 31, 0.72)
                );

            border: 1px solid var(--border-soft);
            border-radius: var(--radius-large);

            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);

            box-shadow: var(--shadow-soft);
        }


        .hero-card {
            padding: 2.4rem;
            margin-bottom: 1.4rem;
        }


        .section-card,
        .glass-card,
        .content-card {
            padding: 1.4rem;
            margin-bottom: 1rem;
        }


        .main-title {
            margin: 0;

            color: var(--text-primary);

            font-size: clamp(2.2rem, 4vw, 3.4rem);
            font-weight: 900;
            line-height: 1.06;
            letter-spacing: -0.045em;
        }


        .subtitle {
            margin-top: 0.75rem;
            margin-bottom: 0;

            color: var(--text-secondary);

            font-size: 1.04rem;
            line-height: 1.6;
        }


        /* =========================================================
           ATHLETE FEATURE GALLERY
        ========================================================= */

        .gallery-heading {
            margin-bottom: 1.8rem;
        }


        .gallery-heading h1 {
            margin: 0.2rem 0 0.35rem;

            font-size: clamp(2.1rem, 4vw, 3.7rem);
            font-weight: 900;
            letter-spacing: -0.045em;
        }


        .gallery-heading p {
            margin: 0;

            color: var(--text-secondary);
            font-size: 1.08rem;
        }


        .gallery-eyebrow {
            color: #60a5fa;

            font-size: 0.75rem;
            font-weight: 800;

            letter-spacing: 0.14em;
            text-transform: uppercase;
        }


        /* Streamlit bordered containers used as feature cards */

        div[data-testid="stVerticalBlockBorderWrapper"] {
            overflow: hidden;

            border: 1px solid rgba(148, 163, 184, 0.18) !important;
            border-radius: 26px !important;

            background:
                linear-gradient(
                    160deg,
                    rgba(12, 21, 39, 0.95),
                    rgba(4, 10, 23, 0.96)
                );

            box-shadow:
                0 22px 60px rgba(0, 0, 0, 0.30);

            transition:
                transform 220ms ease,
                border-color 220ms ease,
                box-shadow 220ms ease;
        }


        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-5px);

            border-color:
                rgba(96, 165, 250, 0.48) !important;

            box-shadow:
                0 30px 76px rgba(0, 0, 0, 0.42),
                0 0 28px rgba(37, 99, 235, 0.10);
        }


        div[data-testid="stVerticalBlockBorderWrapper"]
        > div {
            padding: 1.15rem;
        }


        /* =========================================================
           METRICS
        ========================================================= */

        div[data-testid="stMetric"] {
            min-height: 108px;

            padding: 1rem 1.05rem;

            border-radius: var(--radius-medium);
            border: 1px solid var(--border-soft);

            background:
                linear-gradient(
                    145deg,
                    rgba(15, 23, 42, 0.78),
                    rgba(8, 16, 31, 0.72)
                );

            box-shadow:
                0 14px 34px rgba(0, 0, 0, 0.17);
        }


        div[data-testid="stMetricLabel"] {
            color: var(--text-muted);
            font-size: 0.82rem;
        }


        div[data-testid="stMetricValue"] {
            color: var(--text-primary);
            font-weight: 800;
        }


        /* =========================================================
           BUTTONS — LOGGED-IN PAGES
           Does not override st.form auth submit controls because
           auth_pages.py has stronger scoped selectors.
        ========================================================= */

        .stButton > button {
            min-height: 44px;

            padding: 0.68rem 1.2rem;

            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.13);

            color: white;
            font-weight: 750;

            background:
                linear-gradient(
                    135deg,
                    #2563eb,
                    #06b6d4
                );

            box-shadow:
                0 12px 28px rgba(14, 165, 233, 0.24);

            transition:
                transform 180ms ease,
                box-shadow 180ms ease,
                filter 180ms ease,
                border-color 180ms ease;
        }


        .stButton > button:hover {
            transform: translateY(-2px);
            filter: brightness(1.06);

            border-color: rgba(255, 255, 255, 0.28);

            box-shadow:
                0 18px 40px rgba(14, 165, 233, 0.36);
        }


        .stButton > button:active {
            transform: translateY(0);
        }


        /* =========================================================
           INPUTS — LOGGED-IN PAGES
        ========================================================= */

        div:not([data-testid="stForm"])
        .stTextInput input,

        div:not([data-testid="stForm"])
        .stNumberInput input,

        div:not([data-testid="stForm"])
        .stTextArea textarea {
            color: var(--text-primary) !important;

            border-radius: 14px !important;
            border:
                1px solid
                rgba(148, 163, 184, 0.20) !important;

            background:
                rgba(15, 23, 42, 0.80) !important;
        }


        div:not([data-testid="stForm"])
        .stTextInput input:focus,

        div:not([data-testid="stForm"])
        .stNumberInput input:focus,

        div:not([data-testid="stForm"])
        .stTextArea textarea:focus {
            border-color:
                rgba(56, 189, 248, 0.72) !important;

            box-shadow:
                0 0 0 3px
                rgba(56, 189, 248, 0.10) !important;
        }


        div:not([data-testid="stForm"])
        div[data-baseweb="select"] > div {
            border-radius: 14px !important;

            border:
                1px solid
                rgba(148, 163, 184, 0.20) !important;

            background:
                rgba(15, 23, 42, 0.80) !important;
        }


        /* =========================================================
           ALERTS
        ========================================================= */

        div[data-testid="stAlert"] {
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.14);
        }


        /* =========================================================
           DATAFRAMES AND TABLES
        ========================================================= */

        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            overflow: hidden;

            border-radius: 18px;
            border: 1px solid var(--border-soft);

            background: rgba(6, 13, 26, 0.78);

            box-shadow:
                0 16px 38px rgba(0, 0, 0, 0.18);
        }


        /* =========================================================
           FILE UPLOADER
        ========================================================= */

        section[data-testid="stFileUploaderDropzone"] {
            border-radius: 18px !important;

            border:
                1px dashed
                rgba(96, 165, 250, 0.42) !important;

            background:
                rgba(15, 23, 42, 0.64) !important;

            transition:
                border-color 180ms ease,
                background 180ms ease;
        }


        section[data-testid="stFileUploaderDropzone"]:hover {
            border-color:
                rgba(56, 189, 248, 0.80) !important;

            background:
                rgba(17, 31, 54, 0.78) !important;
        }


        /* =========================================================
           EXPANDERS
        ========================================================= */

        details[data-testid="stExpander"] {
            overflow: hidden;

            border-radius: 16px !important;
            border: 1px solid var(--border-soft) !important;

            background:
                rgba(15, 23, 42, 0.62) !important;
        }


        /* =========================================================
           TABS
        ========================================================= */

        button[data-baseweb="tab"] {
            color: var(--text-secondary);
        }


        button[data-baseweb="tab"][aria-selected="true"] {
            color: #60a5fa;
        }


        /* =========================================================
           SCROLLBAR
        ========================================================= */

        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }


        ::-webkit-scrollbar-track {
            background: rgba(2, 6, 23, 0.88);
        }


        ::-webkit-scrollbar-thumb {
            border-radius: 999px;

            background:
                linear-gradient(
                    180deg,
                    rgba(37, 99, 235, 0.72),
                    rgba(124, 58, 237, 0.68)
                );

            border: 2px solid rgba(2, 6, 23, 0.88);
        }


        /* =========================================================
           RESPONSIVE
        ========================================================= */

        @media (max-width: 1100px) {
            .main .block-container {
                padding-left: 1.1rem;
                padding-right: 1.1rem;
            }
        }


        @media (max-width: 768px) {
            .main .block-container {
                padding-top: 1.6rem;
                padding-bottom: 2rem;
            }

            .hero-card {
                padding: 1.4rem;
                border-radius: 20px;
            }

            div[data-testid="stMetric"] {
                min-height: 94px;
            }
        }
        </style>

        <div class="dashboard-orb dashboard-orb-one"></div>
        <div class="dashboard-orb dashboard-orb-two"></div>
        """,
        unsafe_allow_html=True,
    )