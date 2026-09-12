import streamlit as st
from digital_twin.simulation_engine import simulate_scenario
from database.twin_repository import get_athlete_twin_history

def athlete_simulation():

    st.title(
        "What-if Simulation"
    )

    history_df = (
        get_athlete_twin_history(
            st.session_state.user_id
        )
    )

    if (
        history_df is None
        or history_df.empty
    ):

        st.info(
            "Save at least one Digital Twin state "
            "before running simulations."
        )

        return

    latest_state = (
        history_df
        .sort_values(
            "timestamp"
        )
        .iloc[-1]
        .to_dict()
    )

    sleep_change = st.slider(
        "Change Sleep Hours",
        -4.0,
        4.0,
        0.0,
        0.5,
    )

    training_change = st.slider(
        "Change Training Load",
        -50.0,
        50.0,
        0.0,
        5.0,
    )

    recovery_change = st.slider(
        "Change Recovery Time",
        -5.0,
        5.0,
        0.0,
        0.5,
    )

    simulated = (
        simulate_scenario(
            latest_state,
            sleep_change=(
                sleep_change
            ),
            training_load_change=(
                training_change
            ),
            recovery_change=(
                recovery_change
            ),
        )
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Simulated Fatigue",
        simulated[
            "simulated_fatigue_score"
        ],
    )

    c2.metric(
        "Simulated Readiness",
        (
            f"{simulated['simulated_readiness_score']}%"
        ),
    )

    c3.metric(
        "Simulated Injury Risk",
        simulated[
            "simulated_injury_risk"
        ],
    )
