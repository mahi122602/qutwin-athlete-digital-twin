import os
import psycopg2


def get_connection():
    """
    Database connection priority:

    1. DATABASE_URL
       Used for hosted PostgreSQL / Streamlit deployment.

    2. DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
       Used when individual environment variables are supplied.

    3. Local config.py
       Used only for local development.
    """

    # -----------------------------------------
    # 1. Hosted PostgreSQL connection
    # -----------------------------------------
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)


    # -----------------------------------------
    # 2. Environment-variable connection
    # -----------------------------------------
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_port = os.getenv("DB_PORT", "5432")

    if db_host and db_name and db_user and db_password:
        return psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            port=db_port,
        )


    # -----------------------------------------
    # 3. Local development fallback
    # -----------------------------------------
    try:
        from config import DB_CONFIG

        return psycopg2.connect(**DB_CONFIG)

    except ImportError:
        raise RuntimeError(
            "Database configuration was not found. "
            "Set DATABASE_URL or DB_HOST/DB_NAME/DB_USER/DB_PASSWORD."
        )