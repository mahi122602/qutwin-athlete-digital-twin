from database.connection import get_connection
import pandas as pd


def save_uploaded_file(athlete_id, filename, file_type, rows_extracted):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO uploaded_files
        (athlete_id, filename, file_type, rows_extracted)
        VALUES (%s, %s, %s, %s)
        RETURNING upload_id;
    """, (athlete_id, filename, file_type, rows_extracted))

    upload_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return upload_id


def get_latest_twin_state(athlete_id):
    conn = get_connection()

    df = pd.read_sql("""
        SELECT *
        FROM digital_athlete_state
        WHERE athlete_id = %s
        ORDER BY timestamp DESC
        LIMIT 1;
    """, conn, params=(athlete_id,))

    conn.close()

    if df.empty:
        return None

    return df.iloc[0].to_dict()


def save_digital_twin_states(athlete_id, upload_id, df):
    conn = get_connection()
    cur = conn.cursor()

    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO digital_athlete_state (
                athlete_id,
                upload_id,
                timestamp,
                heart_rate,
                sleep_hours,
                training_load,
                recovery_time,
                hydration_level,
                temperature,
                humidity,
                previous_injury,
                distance,
                avg_speed,
                calories,
                total_ascent,
                duration_minutes,
                acwr,
                recovery_index,
                environmental_stress,
                fatigue_index,
                readiness_index,
                athlete_state,
                twin_score,
                health_index,
                state_explanation,
                fatigue_score,
                injury_risk,
                readiness_score,
                recommendation,
                heart_rate_trend,
                sleep_trend,
                training_load_trend,
                readiness_trend,
                fatigue_trend,
                trend_summary,
                bayesian_fatigue_probability
                prediction_confidence,
                digital_twin_state,
                user_status_message
            )
            VALUES (
                %s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,
                %s,
                %s,%s
            );
        """, (
            athlete_id,
            upload_id,
            row.get("timestamp"),
            row.get("heart_rate"),
            row.get("sleep_hours"),
            row.get("training_load"),
            row.get("recovery_time"),
            row.get("hydration_level"),
            row.get("temperature"),
            row.get("humidity"),
            row.get("previous_injury"),
            row.get("distance"),
            row.get("avg_speed"),
            row.get("calories"),
            row.get("total_ascent"),
            row.get("duration_minutes"),
            row.get("acwr"),
            row.get("recovery_index"),
            row.get("environmental_stress"),
            row.get("fatigue_index"),
            row.get("readiness_index"),
            row.get("athlete_state"),
            row.get("twin_score"),
            row.get("health_index"),
            row.get("state_explanation"),
            row.get("fatigue_score"),
            row.get("injury_risk"),
            row.get("readiness_score"),
            row.get("recommendation"),
            row.get("heart_rate_trend"),
            row.get("sleep_trend"),
            row.get("training_load_trend"),
            row.get("readiness_trend"),
            row.get("fatigue_trend"),
            row.get("trend_summary"),
            row.get("bayesian_fatigue_probability"),
            row.get("prediction_confidence"),
            row.get("digital_twin_state"),
            row.get("user_status_message"),
        ))

    conn.commit()
    cur.close()
    conn.close()


def get_athlete_twin_history(athlete_id):
    conn = get_connection()

    df = pd.read_sql("""
        SELECT *
        FROM digital_athlete_state
        WHERE athlete_id = %s
        ORDER BY timestamp DESC;
    """, conn, params=(athlete_id,))

    conn.close()
    return df