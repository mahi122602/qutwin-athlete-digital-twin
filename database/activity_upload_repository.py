"""Atomic activity uploads with event assignments; existing twin insert fields retained."""
from utils.performance import request_cached, invalidate_reads
import json
from database.connection import get_connection


def _insert_states(cur, athlete_id, upload_id, df):
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
                bayesian_fatigue_probability,
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


@invalidate_reads
def save_activity_upload(athlete_id, filename, file_type, df, content_hash, assignments):
    """Save file metadata, twin rows and event assignments in one transaction.

    The additive metadata table is created on the first successful upload.
    Failure rolls back this file's entire transaction. The unique key prevents
    the same file being inserted twice for one athlete, including after restart.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS qutwin_upload_events (
                    athlete_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    upload_id INTEGER REFERENCES uploaded_files(upload_id),
                    assignments JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (athlete_id, content_hash)
                )
            """)
            cur.execute("""
                INSERT INTO qutwin_upload_events
                    (athlete_id, content_hash, assignments)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (athlete_id, content_hash) DO NOTHING
                RETURNING content_hash
            """, (str(athlete_id), content_hash, json.dumps(assignments)))
            if cur.fetchone() is None:
                cur.execute("""SELECT upload_id FROM qutwin_upload_events
                    WHERE athlete_id = %s AND content_hash = %s""",
                    (str(athlete_id), content_hash))
                upload_id = cur.fetchone()[0]
                conn.commit()
                return {"status": "already_saved", "upload_id": upload_id}
            cur.execute("""
                INSERT INTO uploaded_files (athlete_id, filename, file_type, rows_extracted)
                VALUES (%s, %s, %s, %s) RETURNING upload_id
            """, (athlete_id, filename, file_type, len(df)))
            upload_id = cur.fetchone()[0]
            _insert_states(cur, athlete_id, upload_id, df)
            cur.execute("""UPDATE qutwin_upload_events SET upload_id = %s
                WHERE athlete_id = %s AND content_hash = %s""",
                (upload_id, str(athlete_id), content_hash))
        conn.commit()
        return {"status": "saved", "upload_id": upload_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
