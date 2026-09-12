import streamlit as st
from authentication.session import login_user
from database.athlete_repository import login_athlete
from database.coach_repository import login_coach
from views.auth.shared import _apply_auth_ui, _auth_divider, _brand

def login_page() -> None:

    _apply_auth_ui()

    left, centre, right = st.columns(
        [
            1,
            0.90,
            1,
        ]
    )

    with centre:

        with st.container(
            key="login_card"
        ):

            _brand(
                "Login"
            )

            role = st.selectbox(
                "Role",
                [
                    "Athlete",
                    "Coach",
                ],
                key="login_role",
            )

            user_id = st.text_input(
                "User ID",
                placeholder=(
                    "Enter your User ID"
                ),
                key=(
                    f"login_id_"
                    f"{role.lower()}"
                ),
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder=(
                    "Enter your password"
                ),
                key=(
                    f"login_password_"
                    f"{role.lower()}"
                ),
            )

            login_clicked = st.button(
                "Login",
                use_container_width=True,
                key=(
                    f"login_"
                    f"{role.lower()}"
                ),
            )

            if login_clicked:

                clean_id = (
                    user_id.strip()
                )

                if (
                    not clean_id
                    or not password
                ):

                    st.error(
                        "Enter your ID "
                        "and password."
                    )

                else:

                    success = (
                        login_athlete(
                            clean_id,
                            password,
                        )
                        if role == "Athlete"
                        else login_coach(
                            clean_id,
                            password,
                        )
                    )

                    if success:

                        login_user(
                            role,
                            clean_id,
                        )

                        st.session_state.current_page = (
                            "Athlete Home"
                            if role == "Athlete"
                            else (
                                "Digital Twin Dashboard"
                            )
                        )

                        st.rerun()

                    else:

                        st.error(
                            "Invalid login details."
                        )

            _auth_divider()

            c1, c2 = st.columns(
                2
            )

            with c1:

                if st.button(
                    "Create account",
                    use_container_width=True,
                    key=(
                        "login_create_account"
                    ),
                ):

                    st.session_state.auth_page = (
                        "Signup"
                    )

                    st.rerun()

            with c2:

                if st.button(
                    "Forgot password?",
                    use_container_width=True,
                    key=(
                        "login_forgot_password"
                    ),
                ):

                    st.session_state.auth_page = (
                        "Forgot Password"
                    )

                    st.rerun()
