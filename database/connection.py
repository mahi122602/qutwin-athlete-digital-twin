import os
from database.pool import connect


def get_connection():
    """
    Database connection priority:

    1. DATABASE_URL
       Used for hosted PostgreSQL / Streamlit deployment.

    2. DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
       Used when individual environment variables are supplied.

    3. Top-level Streamlit secrets (DATABASE_URL or complete DB_* fields)
       Used for local or hosted Streamlit configuration.

    4. Local config.py
       Used only for local development.
    """

    # -----------------------------------------
    # 1. Hosted PostgreSQL connection
    # -----------------------------------------
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return connect(database_url)


    # -----------------------------------------
    # 2. Environment-variable connection
    # -----------------------------------------
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_port = os.getenv("DB_PORT", "5432")

    if db_host and db_name and db_user and db_password:
        return connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            port=db_port,
        )


    # Resolve Streamlit secrets explicitly. Root secrets are not loaded until
    # first access; relying on their environment export could switch DBs mid-run.
    try:
        import streamlit as st
        secrets = st.secrets
        secret_url = secrets.get('DATABASE_URL')
        if secret_url:
            return connect(str(secret_url))
        secret_fields = {key: secrets.get('DB_' + key) for key in ('HOST', 'NAME', 'USER', 'PASSWORD')}
        if all(secret_fields.values()):
            return connect(host=secret_fields['HOST'], database=secret_fields['NAME'],
                user=secret_fields['USER'], password=secret_fields['PASSWORD'],
                port=secrets.get('DB_PORT', '5432'))
    except (ImportError, FileNotFoundError, KeyError):
        pass

    # -----------------------------------------
    # 4. Local development fallback
    # -----------------------------------------
    try:
        from config import DB_CONFIG

        return connect(**DB_CONFIG)

    except ImportError:
        raise RuntimeError(
            "Database configuration was not found. "
            "Set DATABASE_URL or DB_HOST/DB_NAME/DB_USER/DB_PASSWORD."
        )
