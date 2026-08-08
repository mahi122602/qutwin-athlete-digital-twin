from database.connection import get_connection
from authentication.password_utils import hash_password, check_password


def register_coach(coach_id, name, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO coaches (coach_id, name, password)
        VALUES (%s, %s, %s)
        ON CONFLICT (coach_id) DO NOTHING;
    """, (
        coach_id,
        name,
        hash_password(password)
    ))

    conn.commit()
    cur.close()
    conn.close()


def login_coach(coach_id, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT password
        FROM coaches
        WHERE coach_id = %s;
    """, (coach_id,))

    result = cur.fetchone()

    cur.close()
    conn.close()

    if result is None:
        return False

    return check_password(password, result[0])


def assign_athlete_to_coach(coach_id, athlete_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO coach_athlete_mapping (coach_id, athlete_id)
        VALUES (%s, %s)
        ON CONFLICT (coach_id, athlete_id) DO NOTHING;
    """, (coach_id, athlete_id))

    conn.commit()
    cur.close()
    conn.close()


def get_assigned_athletes(coach_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            a.athlete_id,
            a.name,
            a.age,
            a.height,
            a.weight,
            a.previous_injury
        FROM coach_athlete_mapping cam
        JOIN athletes a 
            ON cam.athlete_id = a.athlete_id
        WHERE cam.coach_id = %s
        ORDER BY a.name;
    """, (coach_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def get_coach_athlete_risk_dashboard(coach_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            a.athlete_id,
            a.name,
            latest.fatigue_score,
            latest.injury_risk,
            latest.readiness_score,
            latest.twin_score,
            latest.athlete_state,
            latest.recommendation,
            latest.timestamp
        FROM coach_athlete_mapping cam
        JOIN athletes a 
            ON cam.athlete_id = a.athlete_id
        LEFT JOIN LATERAL (
            SELECT *
            FROM digital_athlete_state das
            WHERE das.athlete_id = a.athlete_id
            ORDER BY das.timestamp DESC
            LIMIT 1
        ) latest ON TRUE
        WHERE cam.coach_id = %s
        ORDER BY 
            CASE latest.injury_risk
                WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2
                WHEN 'Low' THEN 3
                ELSE 4
            END,
            latest.fatigue_score DESC NULLS LAST;
    """, (coach_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows