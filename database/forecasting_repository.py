from __future__ import annotations

from contextlib import closing
from datetime import date
import importlib
import json
import os
from typing import Any

import pandas as pd

try:
    import psycopg2
    from psycopg2.extras import Json, RealDictCursor
except ImportError as exc:  # pragma: no cover - handled by application setup
    raise ImportError(
        "psycopg2-binary is required for PostgreSQL access. "
        "Install it with: pip install psycopg2-binary"
    ) from exc


PROFILE_TABLE_CANDIDATES = (
    "athletes",
    "athlete_profile",
    "athlete_profiles",
)


def _get_connection():
    """Reuse the project's existing DB helper when available.

    The fallback environment variables make this module portable without
    forcing the rest of the project to change its database layer.
    """
    candidates = (
        ("database.connection", "get_connection"),
        ("database.connection", "get_db_connection"),
        ("database.db_connection", "get_connection"),
        ("database.db_connection", "get_db_connection"),
        ("database.database", "get_connection"),
    )

    for module_name, function_name in candidates:
        try:
            module = importlib.import_module(module_name)
            function = getattr(module, function_name, None)
            if callable(function):
                return function()
        except (ImportError, AttributeError):
            continue

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    required = {
        "host": os.getenv("DB_HOST"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "port": os.getenv("DB_PORT", "5432"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "No project database helper was found and database environment "
            f"variables are missing: {', '.join(missing)}"
        )
    return psycopg2.connect(**required)


def _discover_profile_table(cursor) -> str | None:
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ANY(%s)
          AND column_name = 'athlete_id'
        GROUP BY table_name
        ORDER BY CASE table_name
            WHEN 'athletes' THEN 1
            WHEN 'athlete_profile' THEN 2
            WHEN 'athlete_profiles' THEN 3
            ELSE 4
        END
        LIMIT 1
        """,
        (list(PROFILE_TABLE_CANDIDATES),),
    )
    row = cursor.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return row["table_name"]
    return row[0]


def ensure_forecasting_schema() -> None:
    with closing(_get_connection()) as connection:
        with connection.cursor() as cursor:
            profile_table = _discover_profile_table(cursor)
            if profile_table:
                cursor.execute(
                    f"ALTER TABLE {profile_table} "
                    "ADD COLUMN IF NOT EXISTS gender VARCHAR(30)"
                )
                cursor.execute(
                    f"ALTER TABLE {profile_table} "
                    "ADD COLUMN IF NOT EXISTS menstrual_tracking_enabled BOOLEAN "
                    "NOT NULL DEFAULT FALSE"
                )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS menstrual_cycle_history (
                    cycle_id BIGSERIAL PRIMARY KEY,
                    athlete_id VARCHAR(100) NOT NULL,
                    period_start_date DATE NOT NULL,
                    period_end_date DATE NOT NULL,
                    symptoms TEXT,
                    athlete_notes TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT valid_period_dates
                        CHECK (period_end_date >= period_start_date),
                    CONSTRAINT reasonable_period_duration
                        CHECK ((period_end_date - period_start_date) BETWEEN 0 AND 14),
                    CONSTRAINT unique_athlete_period_start
                        UNIQUE (athlete_id, period_start_date)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_menstrual_history_athlete_date
                ON menstrual_cycle_history (athlete_id, period_start_date DESC)
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS athlete_forecast_runs (
                    forecast_run_id BIGSERIAL PRIMARY KEY,
                    athlete_id VARCHAR(100) NOT NULL,
                    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    horizon_days INTEGER NOT NULL DEFAULT 7,
                    gender_path VARCHAR(30) NOT NULL,
                    validation_score NUMERIC(8,3),
                    forecast_payload JSONB NOT NULL,
                    evaluation_payload JSONB
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_forecast_runs_athlete_time
                ON athlete_forecast_runs (athlete_id, generated_at DESC)
                """
            )
        connection.commit()


def get_forecasting_profile(athlete_id: str) -> dict[str, Any]:
    with closing(_get_connection()) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            profile_table = _discover_profile_table(cursor)
            if not profile_table:
                return {
                    "athlete_id": athlete_id,
                    "gender": None,
                    "menstrual_tracking_enabled": False,
                }

            cursor.execute(
                f"""
                SELECT athlete_id, gender, menstrual_tracking_enabled
                FROM {profile_table}
                WHERE athlete_id = %s
                LIMIT 1
                """,
                (athlete_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else {
                "athlete_id": athlete_id,
                "gender": None,
                "menstrual_tracking_enabled": False,
            }


def set_athlete_gender(athlete_id: str, gender: str) -> None:
    clean_gender = (gender or "").strip()
    if not clean_gender:
        raise ValueError("Gender cannot be empty.")

    with closing(_get_connection()) as connection:
        with connection.cursor() as cursor:
            profile_table = _discover_profile_table(cursor)
            if not profile_table:
                raise RuntimeError(
                    "No athlete profile table containing athlete_id was found."
                )
            cursor.execute(
                f"UPDATE {profile_table} SET gender = %s WHERE athlete_id = %s",
                (clean_gender, athlete_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Athlete profile {athlete_id!r} was not found.")
        connection.commit()


def set_menstrual_tracking_enabled(athlete_id: str, enabled: bool) -> None:
    with closing(_get_connection()) as connection:
        with connection.cursor() as cursor:
            profile_table = _discover_profile_table(cursor)
            if not profile_table:
                raise RuntimeError(
                    "No athlete profile table containing athlete_id was found."
                )
            cursor.execute(
                f"""
                UPDATE {profile_table}
                SET menstrual_tracking_enabled = %s
                WHERE athlete_id = %s
                """,
                (bool(enabled), athlete_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Athlete profile {athlete_id!r} was not found.")
        connection.commit()


def add_menstrual_cycle(
    athlete_id: str,
    period_start_date: date,
    period_end_date: date,
    symptoms: str | None = None,
    athlete_notes: str | None = None,
) -> None:
    if period_end_date < period_start_date:
        raise ValueError("Period end date cannot be before the start date.")
    duration = (period_end_date - period_start_date).days + 1
    if duration > 15:
        raise ValueError("Period duration must be 15 days or fewer.")

    with closing(_get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO menstrual_cycle_history (
                    athlete_id,
                    period_start_date,
                    period_end_date,
                    symptoms,
                    athlete_notes
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (athlete_id, period_start_date)
                DO UPDATE SET
                    period_end_date = EXCLUDED.period_end_date,
                    symptoms = EXCLUDED.symptoms,
                    athlete_notes = EXCLUDED.athlete_notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    athlete_id,
                    period_start_date,
                    period_end_date,
                    symptoms,
                    athlete_notes,
                ),
            )
        connection.commit()


def get_menstrual_history(athlete_id: str) -> pd.DataFrame:
    with closing(_get_connection()) as connection:
        query = """
            SELECT
                cycle_id,
                period_start_date,
                period_end_date,
                (period_end_date - period_start_date + 1) AS days_periods,
                symptoms,
                athlete_notes,
                created_at,
                updated_at
            FROM menstrual_cycle_history
            WHERE athlete_id = %s
            ORDER BY period_start_date ASC, cycle_id ASC
        """
        return pd.read_sql_query(query, connection, params=(athlete_id,))


def replace_menstrual_history(
    athlete_id: str,
    edited_df: pd.DataFrame,
    existing_df: pd.DataFrame | None = None,
) -> None:
    """Persist edits, additions and deletions from st.data_editor."""
    edited = edited_df.copy()
    if edited.empty:
        edited_ids: set[int] = set()
    else:
        for column in ("period_start_date", "period_end_date"):
            edited[column] = pd.to_datetime(edited[column], errors="coerce").dt.date
        if edited[["period_start_date", "period_end_date"]].isna().any().any():
            raise ValueError("Every row must contain valid start and end dates.")
        invalid = edited["period_end_date"] < edited["period_start_date"]
        if invalid.any():
            raise ValueError("An end date cannot be before its start date.")
        durations = (
            pd.to_datetime(edited["period_end_date"])
            - pd.to_datetime(edited["period_start_date"])
        ).dt.days + 1
        if (durations > 15).any():
            raise ValueError("Period duration must be 15 days or fewer.")

        edited_ids = {
            int(value)
            for value in edited.get("cycle_id", pd.Series(dtype=float)).dropna()
        }

    existing_ids: set[int] = set()
    if existing_df is not None and not existing_df.empty and "cycle_id" in existing_df:
        existing_ids = {
            int(value) for value in existing_df["cycle_id"].dropna().tolist()
        }
    deleted_ids = existing_ids - edited_ids

    with closing(_get_connection()) as connection:
        with connection.cursor() as cursor:
            if deleted_ids:
                cursor.execute(
                    """
                    DELETE FROM menstrual_cycle_history
                    WHERE athlete_id = %s AND cycle_id = ANY(%s)
                    """,
                    (athlete_id, list(deleted_ids)),
                )

            for _, row in edited.iterrows():
                cycle_id = row.get("cycle_id")
                symptoms = row.get("symptoms")
                notes = row.get("athlete_notes")
                start_date = row["period_start_date"]
                end_date = row["period_end_date"]

                if pd.notna(cycle_id):
                    cursor.execute(
                        """
                        UPDATE menstrual_cycle_history
                        SET
                            period_start_date = %s,
                            period_end_date = %s,
                            symptoms = %s,
                            athlete_notes = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE cycle_id = %s AND athlete_id = %s
                        """,
                        (
                            start_date,
                            end_date,
                            None if pd.isna(symptoms) else str(symptoms),
                            None if pd.isna(notes) else str(notes),
                            int(cycle_id),
                            athlete_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO menstrual_cycle_history (
                            athlete_id,
                            period_start_date,
                            period_end_date,
                            symptoms,
                            athlete_notes
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (athlete_id, period_start_date)
                        DO UPDATE SET
                            period_end_date = EXCLUDED.period_end_date,
                            symptoms = EXCLUDED.symptoms,
                            athlete_notes = EXCLUDED.athlete_notes,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            athlete_id,
                            start_date,
                            end_date,
                            None if pd.isna(symptoms) else str(symptoms),
                            None if pd.isna(notes) else str(notes),
                        ),
                    )
        connection.commit()


def save_forecast_run(
    athlete_id: str,
    gender_path: str,
    validation_score: float | None,
    forecast_df: pd.DataFrame,
    evaluation_df: pd.DataFrame | None = None,
) -> int:
    forecast_payload = json.loads(
        forecast_df.to_json(orient="records", date_format="iso")
    )
    evaluation_payload = (
        json.loads(evaluation_df.to_json(orient="records", date_format="iso"))
        if evaluation_df is not None and not evaluation_df.empty
        else []
    )

    with closing(_get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO athlete_forecast_runs (
                    athlete_id,
                    horizon_days,
                    gender_path,
                    validation_score,
                    forecast_payload,
                    evaluation_payload
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING forecast_run_id
                """,
                (
                    athlete_id,
                    int(len(forecast_df)),
                    gender_path,
                    validation_score,
                    Json(forecast_payload),
                    Json(evaluation_payload),
                ),
            )
            forecast_run_id = int(cursor.fetchone()[0])
        connection.commit()
    return forecast_run_id
