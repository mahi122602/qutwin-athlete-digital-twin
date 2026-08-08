from database.connection import get_connection
from authentication.password_utils import hash_password, check_password


def register_athlete(athlete_id, name, password, age, height, weight, previous_injury):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO athletes 
        (athlete_id, name, password, age, height, weight, previous_injury)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (athlete_id) DO NOTHING;
    """, (
        athlete_id,
        name,
        hash_password(password),
        age,
        height,
        weight,
        previous_injury
    ))

    conn.commit()
    cur.close()
    conn.close()


def login_athlete(athlete_id, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT password FROM athletes WHERE athlete_id=%s", (athlete_id,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result is None:
        return False

    return check_password(password, result[0])


def get_athlete_profile(athlete_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            athlete_id,
            name,
            age,
            height,
            weight,
            previous_injury,
            email,
            contact_number,
            injury_history,
            profile_photo
        FROM athletes
        WHERE athlete_id = %s;
    """, (athlete_id,))

    row = cur.fetchone()

    cur.close()
    conn.close()

    if row is None:
        return None

    return {
        "athlete_id": row[0],
        "name": row[1],
        "age": row[2],
        "height": row[3],
        "weight": row[4],
        "previous_injury": row[5],
        "email": row[6],
        "contact_number": row[7],
        "injury_history": row[8],
        "profile_photo": row[9],
    }


def update_athlete_profile(
    athlete_id,
    name,
    email,
    contact_number,
    height,
    weight,
    injury_history,
    profile_photo=None,
):
    conn = get_connection()
    cur = conn.cursor()

    if profile_photo is not None:
        cur.execute("""
            UPDATE athletes
            SET 
                name = %s,
                email = %s,
                contact_number = %s,
                height = %s,
                weight = %s,
                injury_history = %s,
                profile_photo = %s
            WHERE athlete_id = %s;
        """, (
            name,
            email,
            contact_number,
            height,
            weight,
            injury_history,
            profile_photo,
            athlete_id,
        ))
    else:
        cur.execute("""
            UPDATE athletes
            SET 
                name = %s,
                email = %s,
                contact_number = %s,
                height = %s,
                weight = %s,
                injury_history = %s
            WHERE athlete_id = %s;
        """, (
            name,
            email,
            contact_number,
            height,
            weight,
            injury_history,
            athlete_id,
        ))

    conn.commit()
    cur.close()
    conn.close()