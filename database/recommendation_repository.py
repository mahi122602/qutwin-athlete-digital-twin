from database.connection import get_connection
import pandas as pd


def save_coach_recommendation(
    coach_id,
    athlete_id,
    ai_recommendation,
    coach_comment,
    approval_status,
):
    conn = get_connection()
    cur = conn.cursor()

    final_recommendation = coach_comment if coach_comment else ai_recommendation

    cur.execute("""
        INSERT INTO coach_recommendations (
            coach_id,
            athlete_id,
            ai_recommendation,
            coach_comment,
            recommendation,
            approval_status,
            reviewed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
    """, (
        coach_id,
        athlete_id,
        ai_recommendation,
        coach_comment,
        final_recommendation,
        approval_status,
    ))

    conn.commit()
    cur.close()
    conn.close()


def get_latest_coach_recommendation(athlete_id):
    conn = get_connection()

    df = pd.read_sql("""
        SELECT
            recommendation,
            ai_recommendation,
            coach_comment,
            coach_id,
            approval_status,
            reviewed_at,
            created_at
        FROM coach_recommendations
        WHERE athlete_id = %s
          AND approval_status = 'Approved'
        ORDER BY reviewed_at DESC, created_at DESC
        LIMIT 1;
    """, conn, params=(athlete_id,))

    conn.close()

    if df.empty:
        return None

    return df.iloc[0].to_dict()


def get_coach_recommendation_history(athlete_id):
    conn = get_connection()

    df = pd.read_sql("""
        SELECT *
        FROM coach_recommendations
        WHERE athlete_id = %s
        ORDER BY created_at DESC;
    """, conn, params=(athlete_id,))

    conn.close()
    return df