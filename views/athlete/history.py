import streamlit as st
import pandas as pd
import plotly.express as px
from database.twin_repository import get_athlete_twin_history

def athlete_history():

    st.title(
        "Digital Twin History"
    )

    st.caption(
        "Understand your past performance, recovery, "
        "training load, and Digital Twin state through "
        "interactive visuals."
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
            "No Digital Twin history "
            "available yet."
        )

        return

    history_df = history_df.copy()

    # --------------------------------------------------------
    # PREPARE DATA
    # --------------------------------------------------------

    if "timestamp" in history_df.columns:

        history_df[
            "timestamp"
        ] = pd.to_datetime(
            history_df["timestamp"],
            errors="coerce",
        )

    history_df = (
        history_df.sort_values(
            "timestamp"
        )
    )

    latest = history_df.iloc[-1]

    previous = (
        history_df.iloc[-2]
        if len(history_df) > 1
        else None
    )

    def safe_value(
        row,
        key,
        default=0,
    ):

        try:

            value = row.get(
                key,
                default,
            )

            if pd.isna(value):

                return default

            return value

        except Exception:

            return default

    def safe_delta(
        current,
        previous_value,
    ):

        if previous_value is None:

            return None

        try:

            return round(
                float(current)
                - float(previous_value),
                1,
            )

        except Exception:

            return None

    def format_metric(
        value,
    ):

        try:

            return (
                f"{float(value):.1f}"
            )

        except (
            TypeError,
            ValueError,
        ):

            return "N/A"

    # --------------------------------------------------------
    # LATEST SNAPSHOT
    # --------------------------------------------------------

    st.markdown(
        "## Latest Snapshot"
    )

    fatigue = safe_value(
        latest,
        "fatigue_score",
    )

    readiness = safe_value(
        latest,
        "readiness_score",
    )

    twin_score = safe_value(
        latest,
        "twin_score",
    )

    health_index = safe_value(
        latest,
        "health_index",
    )

    injury_risk = safe_value(
        latest,
        "injury_risk",
        "Unknown",
    )

    athlete_state = safe_value(
        latest,
        "athlete_state",
        "Unknown",
    )

    recommendation = safe_value(
        latest,
        "recommendation",
        "No recommendation available.",
    )

    prev_fatigue = (
        safe_value(
            previous,
            "fatigue_score",
        )
        if previous is not None
        else None
    )

    prev_readiness = (
        safe_value(
            previous,
            "readiness_score",
        )
        if previous is not None
        else None
    )

    prev_twin = (
        safe_value(
            previous,
            "twin_score",
        )
        if previous is not None
        else None
    )

    prev_health = (
        safe_value(
            previous,
            "health_index",
        )
        if previous is not None
        else None
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Fatigue",
        format_metric(fatigue),
        delta=safe_delta(
            fatigue,
            prev_fatigue,
        ),
    )

    c2.metric(
        "Readiness",
        format_metric(readiness),
        delta=safe_delta(
            readiness,
            prev_readiness,
        ),
    )

    c3.metric(
        "Twin Score",
        format_metric(twin_score),
        delta=safe_delta(
            twin_score,
            prev_twin,
        ),
    )

    c4.metric(
        "Health Index",
        format_metric(health_index),
        delta=safe_delta(
            health_index,
            prev_health,
        ),
    )

    c5, c6 = st.columns(2)

    c5.markdown(
        f"""
        <div style="
            background: rgba(0, 180, 255, 0.12);
            padding: 18px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <h4 style="margin-bottom:6px;">
                Injury Risk
            </h4>
            <h2 style="margin-top:0;">
                {injury_risk}
            </h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c6.markdown(
        f"""
        <div style="
            background: rgba(0, 255, 180, 0.10);
            padding: 18px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.08);
        ">
            <h4 style="margin-bottom:6px;">
                Athlete State
            </h4>
            <h2 style="margin-top:0;">
                {athlete_state}
            </h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "### Latest Recommendation"
    )

    st.info(
        recommendation
    )

    # --------------------------------------------------------
    # VISUAL PERFORMANCE OVERVIEW
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown(
        "## Visual Performance Overview"
    )

    st.caption(
        "These visuals help you quickly understand "
        "how your body and Digital Twin state have "
        "changed over time."
    )

    # --------------------------------------------------------
    # SIDE-BY-SIDE VISUALS
    # --------------------------------------------------------

    left_chart, right_chart = (
        st.columns(
            [1.6, 1],
            gap="large",
        )
    )

    # ========================================================
    # DIGITAL TWIN TRENDS
    # ========================================================

    with left_chart:

        st.markdown(
            "### Digital Twin Trends Over Time"
        )

        st.caption(
            "See how fatigue, readiness, Twin Score, "
            "and Health Index have changed across your "
            "recorded Digital Twin states."
        )

        trend_columns = [
            "fatigue_score",
            "readiness_score",
            "twin_score",
            "health_index",
        ]

        available_trend_columns = [
            column
            for column in trend_columns
            if column
            in history_df.columns
        ]

        if (
            available_trend_columns
            and "timestamp"
            in history_df.columns
        ):

            trend_df = history_df[
                [
                    "timestamp",
                    *available_trend_columns,
                ]
            ].copy()

            trend_df = trend_df.rename(
                columns={
                    "fatigue_score":
                        "Fatigue",
                    "readiness_score":
                        "Readiness",
                    "twin_score":
                        "Twin Score",
                    "health_index":
                        "Health Index",
                }
            )

            melted = trend_df.melt(
                id_vars="timestamp",
                var_name="Metric",
                value_name="Score",
            )

            fig_trend = px.line(
                melted,
                x="timestamp",
                y="Score",
                color="Metric",
                markers=True,
            )

            fig_trend.update_traces(
                line=dict(
                    width=3,
                ),
                marker=dict(
                    size=8,
                ),
            )

            fig_trend.update_layout(
                height=430,
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20,
                ),
                xaxis_title=(
                    "Date / Time"
                ),
                yaxis_title="Score",
                legend_title="Metric",
                hovermode="x unified",
            )

            fig_trend.update_yaxes(
                range=[
                    0,
                    100,
                ]
            )

            st.plotly_chart(
                fig_trend,
                use_container_width=True,
                key=(
                    "history_trend_chart"
                ),
            )

        else:

            st.info(
                "Not enough historical information "
                "is available for the trend chart yet."
            )

    # ========================================================
    # LATEST ATHLETE CONDITION PROFILE
    # ========================================================

    with right_chart:

        st.markdown(
            "### Latest Athlete Condition Profile"
        )

        st.caption(
            "A quick visual summary of your "
            "latest Digital Twin condition."
        )

        latest_profile = pd.DataFrame(
            {
                "Metric": [
                    "Fatigue",
                    "Readiness",
                    "Twin Score",
                    "Health Index",
                    "Training Load",
                    "Recovery",
                    "Sleep",
                ],

                "Score": [
                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "fatigue_score",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "readiness_score",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "twin_score",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "health_index",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            float(
                                safe_value(
                                    latest,
                                    "training_load",
                                    0,
                                )
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            (
                                float(
                                    safe_value(
                                        latest,
                                        "recovery_time",
                                        0,
                                    )
                                )
                                / 12
                                * 100
                            ),
                            0,
                        ),
                        100,
                    ),

                    min(
                        max(
                            (
                                float(
                                    safe_value(
                                        latest,
                                        "sleep_hours",
                                        0,
                                    )
                                )
                                / 10
                                * 100
                            ),
                            0,
                        ),
                        100,
                    ),
                ],

                "Actual value": [
                    (
                        f"{float(safe_value(latest, 'fatigue_score', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'readiness_score', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'twin_score', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'health_index', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'training_load', 0)):.1f}"
                    ),
                    (
                        f"{float(safe_value(latest, 'recovery_time', 0)):.1f} h"
                    ),
                    (
                        f"{float(safe_value(latest, 'sleep_hours', 0)):.1f} h"
                    ),
                ],
            }
        )

        fig_profile = px.pie(
            latest_profile,
            names="Metric",
            values="Score",
            hole=0.52,
            custom_data=[
                "Actual value",
            ],
        )

        fig_profile.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate=(
                "<b>%{label}</b>"
                "<br>Actual value: "
                "%{customdata[0]}"
                "<br>Profile share: "
                "%{percent}"
                "<extra></extra>"
            ),
        )

        fig_profile.update_layout(
            height=430,
            margin=dict(
                l=10,
                r=10,
                t=20,
                b=20,
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.20,
                xanchor="center",
                x=0.5,
            ),
            annotations=[
                dict(
                    text=(
                        "Latest<br>"
                        "Condition"
                    ),
                    x=0.5,
                    y=0.5,
                    font_size=18,
                    showarrow=False,
                )
            ],
        )

        st.plotly_chart(
            fig_profile,
            use_container_width=True,
            key=(
                "latest_condition_profile"
            ),
        )

    # --------------------------------------------------------
    # SECOND VISUAL ROW
    # --------------------------------------------------------

    risk_col, state_col = (
        st.columns(
            [1.6, 1],
            gap="large",
        )
    )

    # ========================================================
    # INJURY RISK TIMELINE
    # ========================================================

    with risk_col:

        st.markdown(
            "### Injury Risk Timeline"
        )

        st.caption(
            "See how your injury-risk level relates "
            "to fatigue across your recorded "
            "Digital Twin states."
        )

        if (
            "injury_risk"
            in history_df.columns
            and "timestamp"
            in history_df.columns
            and "fatigue_score"
            in history_df.columns
        ):

            risk_timeline = (
                history_df.copy()
            )

            hover_columns = [
                column
                for column in [
                    "readiness_score",
                    "athlete_state",
                    "recommendation",
                ]
                if column
                in risk_timeline.columns
            ]

            fig_risk = px.bar(
                risk_timeline,
                x="timestamp",
                y="fatigue_score",
                color="injury_risk",
                hover_data=(
                    hover_columns
                ),
                labels={
                    "timestamp":
                        "Date / Time",
                    "fatigue_score":
                        "Fatigue Score",
                    "injury_risk":
                        "Injury Risk",
                },
            )

            fig_risk.update_traces(
                texttemplate="%{y:.1f}",
                textposition="outside",
                marker=dict(
                    opacity=0.85,
                    line=dict(
                        width=1,
                    ),
                ),
                hovertemplate=(
                    "<b>%{x}</b>"
                    "<br>Fatigue Score: "
                    "%{y:.1f}"
                    "<br>Injury Risk: "
                    "%{fullData.name}"
                    "<extra></extra>"
                ),
            )

            fig_risk.update_layout(
                height=420,
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20,
                ),
                xaxis_title=(
                    "Date / Time"
                ),
                yaxis_title=(
                    "Fatigue Score"
                ),
                legend_title=(
                    "Injury Risk"
                ),
                bargap=0.35,
            )

            fig_risk.update_yaxes(
                range=[
                    0,
                    100,
                ]
            )

            st.plotly_chart(
                fig_risk,
                use_container_width=True,
                key=(
                    "history_injury_risk_chart"
                ),
            )

        else:

            st.info(
                "Not enough information is available "
                "for the injury-risk timeline yet."
            )

    # ========================================================
    # ATHLETE STATE DISTRIBUTION
    # ========================================================

    with state_col:

        st.markdown(
            "### Athlete State History"
        )

        st.caption(
            "See how often your Digital Twin has "
            "classified you in each athlete state."
        )

        if (
            "athlete_state"
            in history_df.columns
        ):

            state_counts = (
                history_df[
                    "athlete_state"
                ]
                .fillna("Unknown")
                .value_counts()
                .reset_index()
            )

            state_counts.columns = [
                "Athlete State",
                "Count",
            ]

            fig_state = px.pie(
                state_counts,
                names="Athlete State",
                values="Count",
                hole=0.55,
            )

            fig_state.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate=(
                    "<b>%{label}</b>"
                    "<br>Recorded states: "
                    "%{value}"
                    "<br>Share: "
                    "%{percent}"
                    "<extra></extra>"
                ),
            )

            fig_state.update_layout(
                height=420,
                margin=dict(
                    l=10,
                    r=10,
                    t=20,
                    b=20,
                ),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.18,
                    xanchor="center",
                    x=0.5,
                ),
                annotations=[
                    dict(
                        text=(
                            "State<br>"
                            "History"
                        ),
                        x=0.5,
                        y=0.5,
                        font_size=17,
                        showarrow=False,
                    )
                ],
            )

            st.plotly_chart(
                fig_state,
                use_container_width=True,
                key=(
                    "history_state_distribution"
                ),
            )

    # --------------------------------------------------------
    # SIMPLE INTERPRETATION
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown(
        "## Simple Interpretation"
    )

    insight_cols = st.columns(3)

    insight_cols[0].success(
        f"**Fatigue:** "
        f"{format_metric(fatigue)}\n\n"
        "This shows how physically tired "
        "your body currently is."
    )

    insight_cols[1].info(
        f"**Readiness:** "
        f"{format_metric(readiness)}\n\n"
        "This reflects how prepared your body "
        "is for training or performance."
    )

    insight_cols[2].warning(
        f"**Injury Risk:** "
        f"{injury_risk}\n\n"
        "This indicates your current potential "
        "risk level based on your latest state."
    )

    # --------------------------------------------------------
    # DETAILED HISTORY TABLE
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown(
        "## Detailed History Records"
    )

    st.caption(
        "Scroll through the complete history "
        "in simplified athlete-friendly wording."
    )

    display_df = (
        history_df.copy()
    )

    rename_map = {
        "timestamp":
            "Date / Time",
        "heart_rate":
            "Heart Rate",
        "sleep_hours":
            "Sleep Hours",
        "training_load":
            "Training Load",
        "recovery_time":
            "Recovery Time",
        "fatigue_score":
            "Fatigue",
        "readiness_score":
            "Readiness",
        "injury_risk":
            "Injury Risk",
        "athlete_state":
            "Athlete State",
        "twin_score":
            "Twin Score",
        "health_index":
            "Health Index",
        "recommendation":
            "Recommendation",
    }

    preferred_columns = [
        "timestamp",
        "heart_rate",
        "sleep_hours",
        "training_load",
        "recovery_time",
        "fatigue_score",
        "readiness_score",
        "injury_risk",
        "athlete_state",
        "twin_score",
        "health_index",
        "recommendation",
    ]

    available_columns = [
        column
        for column
        in preferred_columns
        if column
        in display_df.columns
    ]

    display_df = (
        display_df[
            available_columns
        ]
        .rename(
            columns=rename_map
        )
    )

    if (
        "Date / Time"
        in display_df.columns
    ):

        display_df[
            "Date / Time"
        ] = (
            pd.to_datetime(
                display_df[
                    "Date / Time"
                ],
                errors="coerce",
            )
            .dt.strftime(
                "%d %b %Y, %H:%M"
            )
        )

    if (
        "Heart Rate"
        in display_df.columns
    ):

        display_df[
            "Heart Rate"
        ] = display_df[
            "Heart Rate"
        ].apply(
            lambda value: (
                f"{value:.0f} bpm"
                if pd.notna(value)
                else "-"
            )
        )

    if (
        "Sleep Hours"
        in display_df.columns
    ):

        display_df[
            "Sleep Hours"
        ] = display_df[
            "Sleep Hours"
        ].apply(
            lambda value: (
                f"{value:.1f} h"
                if pd.notna(value)
                else "-"
            )
        )

    if (
        "Recovery Time"
        in display_df.columns
    ):

        display_df[
            "Recovery Time"
        ] = display_df[
            "Recovery Time"
        ].apply(
            lambda value: (
                f"{value:.1f} h"
                if pd.notna(value)
                else "-"
            )
        )

    st.dataframe(
        display_df.iloc[::-1],
        use_container_width=True,
        hide_index=True,
    )

    csv = (
        display_df
        .iloc[::-1]
        .to_csv(
            index=False
        )
        .encode("utf-8")
    )

    st.download_button(
        "Download History CSV",
        csv,
        "digital_twin_history.csv",
        "text/csv",
    )
