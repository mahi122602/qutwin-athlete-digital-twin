import streamlit as st
from views.auth.shared import _apply_auth_ui, _auth_divider, _brand

def forgot_password_page() -> None:

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
            key="reset_card"
        ):

            _brand(
                "Reset Password"
            )

            role = st.selectbox(
                "Account type",
                [
                    "Athlete",
                    "Coach",
                ],
                key="reset_role",
            )

            user_id = st.text_input(
                "User ID",
                placeholder=(
                    "Enter your User ID"
                ),
                key=(
                    f"reset_id_"
                    f"{role.lower()}"
                ),
            )

            email = st.text_input(
                "Registered email",
                placeholder=(
                    "Enter your registered email"
                ),
                key=(
                    f"reset_email_"
                    f"{role.lower()}"
                ),
            )

            if st.button(
                "Send reset request",
                use_container_width=True,
                key="reset_submit",
            ):

                if (
                    not user_id.strip()
                    or not email.strip()
                ):

                    st.error(
                        "Enter your ID "
                        "and email."
                    )

                else:

                    st.info(
                        "Password reset email "
                        "still needs to be connected."
                    )

            _auth_divider()

            if st.button(
                "Back to login",
                use_container_width=True,
                key="reset_back_login",
            ):

                st.session_state.auth_page = (
                    "Login"
                )

                st.rerun()
