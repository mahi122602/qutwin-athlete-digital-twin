import streamlit as st
from database.athlete_repository import register_athlete
from database.coach_repository import register_coach
from views.auth.shared import _apply_auth_ui, _auth_divider, _brand

def signup_page() -> None:

    _apply_auth_ui()

    left, centre, right = st.columns(
        [
            1,
            1.05,
            1,
        ]
    )

    with centre:

        with st.container(
            key="signup_card"
        ):

            _brand(
                "Create Account"
            )

            role = st.selectbox(
                "Create account as",
                [
                    "Athlete",
                    "Coach",
                ],
                key="signup_role",
            )

            user_id = st.text_input(
                "User ID",
                placeholder=(
                    "Choose your User ID"
                ),
                key=(
                    f"signup_id_"
                    f"{role.lower()}"
                ),
            )

            name = st.text_input(
                "Full name",
                placeholder=(
                    "Enter your full name"
                ),
                key=(
                    f"signup_name_"
                    f"{role.lower()}"
                ),
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder=(
                    "Create a password"
                ),
                key=(
                    f"signup_password_"
                    f"{role.lower()}"
                ),
            )

            confirm = st.text_input(
                "Confirm password",
                type="password",
                placeholder=(
                    "Enter your password again"
                ),
                key=(
                    f"signup_confirm_"
                    f"{role.lower()}"
                ),
            )

            athlete_values = None

            if role == "Athlete":

                a, b = st.columns(
                    2
                )

                with a:

                    age = st.number_input(
                        "Age",
                        10,
                        80,
                        22,
                    )

                    weight = (
                        st.number_input(
                            "Weight (kg)",
                            30.0,
                            250.0,
                            70.0,
                        )
                    )

                with b:

                    height = (
                        st.number_input(
                            "Height (cm)",
                            100.0,
                            250.0,
                            170.0,
                        )
                    )

                    previous_injury = (
                        st.number_input(
                            "Previous injuries",
                            0,
                            30,
                            0,
                        )
                    )

                athlete_values = (
                    age,
                    height,
                    weight,
                    previous_injury,
                )

            if st.button(
                f"Create {role} account",
                use_container_width=True,
                key=(
                    f"signup_submit_"
                    f"{role.lower()}"
                ),
            ):

                if (
                    not user_id.strip()
                    or not name.strip()
                    or not password
                ):

                    st.error(
                        "Complete all "
                        "required fields."
                    )

                elif (
                    password
                    != confirm
                ):

                    st.error(
                        "Passwords do not match."
                    )

                else:

                    if role == "Athlete":

                        (
                            age,
                            height,
                            weight,
                            previous_injury,
                        ) = athlete_values

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

                        register_coach(
                            user_id.strip(),
                            name.strip(),
                            password,
                        )

                    st.session_state.auth_page = (
                        "Login"
                    )

                    st.rerun()

            _auth_divider()

            if st.button(
                "Back to login",
                use_container_width=True,
                key="signup_back_login",
            ):

                st.session_state.auth_page = (
                    "Login"
                )

                st.rerun()
