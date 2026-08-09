from database.connection import get_connection


def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    try:
        # =========================================================
        # ATHLETES
        # =========================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS athletes (
                athlete_id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                password TEXT NOT NULL,

                age INT,
                height FLOAT,
                weight FLOAT,
                previous_injury INT DEFAULT 0,

                email VARCHAR(255),
                contact_number VARCHAR(50),
                injury_history TEXT,
                profile_photo BYTEA,

                gender VARCHAR(30),
                menstrual_tracking_enabled BOOLEAN DEFAULT FALSE,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ---------------------------------------------------------
        # Make older athlete tables compatible with current code.
        # These commands are safe if the columns already exist.
        # ---------------------------------------------------------
        cur.execute("""
            ALTER TABLE athletes
            ADD COLUMN IF NOT EXISTS email VARCHAR(255);
        """)

        cur.execute("""
            ALTER TABLE athletes
            ADD COLUMN IF NOT EXISTS contact_number VARCHAR(50);
        """)

        cur.execute("""
            ALTER TABLE athletes
            ADD COLUMN IF NOT EXISTS injury_history TEXT;
        """)

        cur.execute("""
            ALTER TABLE athletes
            ADD COLUMN IF NOT EXISTS profile_photo BYTEA;
        """)

        cur.execute("""
            ALTER TABLE athletes
            ADD COLUMN IF NOT EXISTS gender VARCHAR(30);
        """)

        cur.execute("""
            ALTER TABLE athletes
            ADD COLUMN IF NOT EXISTS menstrual_tracking_enabled
            BOOLEAN DEFAULT FALSE;
        """)

        # =========================================================
        # COACHES
        # =========================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coaches (
                coach_id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # =========================================================
        # COACH ↔ ATHLETE MAPPING
        # =========================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coach_athlete_mapping (
                mapping_id SERIAL PRIMARY KEY,
                coach_id VARCHAR(50)
                    REFERENCES coaches(coach_id),
                athlete_id VARCHAR(50)
                    REFERENCES athletes(athlete_id),
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(coach_id, athlete_id)
            );
        """)

        # =========================================================
        # UPLOADED FILES
        # =========================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                upload_id SERIAL PRIMARY KEY,
                athlete_id VARCHAR(50)
                    REFERENCES athletes(athlete_id),
                filename TEXT,
                file_type VARCHAR(50),
                rows_extracted INT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # =========================================================
        # DIGITAL ATHLETE STATE
        # =========================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS digital_athlete_state (
                state_id SERIAL PRIMARY KEY,

                athlete_id VARCHAR(50)
                    REFERENCES athletes(athlete_id),

                upload_id INT
                    REFERENCES uploaded_files(upload_id),

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

        # =========================================================
        # SAVE DATABASE CHANGES
        # =========================================================
        conn.commit()

        print("✅ Database tables updated successfully.")

    except Exception as error:
        conn.rollback()
        print(f"❌ Database setup failed: {error}")
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    create_tables()