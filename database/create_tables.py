from database.connection import get_connection

def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS athletes (
        athlete_id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        password TEXT NOT NULL,
        age INT,
        height FLOAT,
        weight FLOAT,
        previous_injury INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS coaches (
        coach_id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS coach_athlete_mapping (
        mapping_id SERIAL PRIMARY KEY,
        coach_id VARCHAR(50) REFERENCES coaches(coach_id),
        athlete_id VARCHAR(50) REFERENCES athletes(athlete_id),
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(coach_id, athlete_id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS uploaded_files (
        upload_id SERIAL PRIMARY KEY,
        athlete_id VARCHAR(50) REFERENCES athletes(athlete_id),
        filename TEXT,
        file_type VARCHAR(50),
        rows_extracted INT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS digital_athlete_state (
        state_id SERIAL PRIMARY KEY,
        athlete_id VARCHAR(50) REFERENCES athletes(athlete_id),
        upload_id INT REFERENCES uploaded_files(upload_id),
        timestamp TIMESTAMP,
        heart_rate FLOAT,
        sleep_hours FLOAT,
        training_load FLOAT,
        recovery_time FLOAT,
        hydration_level VARCHAR(50),
        temperature FLOAT,
        humidity FLOAT,
        previous_injury INT,
        distance FLOAT,
        avg_speed FLOAT,
        calories FLOAT,
        total_ascent FLOAT,
        duration_minutes FLOAT,
        fatigue_score FLOAT,
        injury_risk VARCHAR(50),
        readiness_score FLOAT,
        athlete_state VARCHAR(50),
        recommendation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database tables updated successfully.")

if __name__ == "__main__":
    create_tables()