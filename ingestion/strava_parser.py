import io
import zipfile

import pandas as pd

from preprocessing.feature_engineering import safe_float


def _get_bytes(uploaded_file):
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()

    uploaded_file.seek(0)
    return uploaded_file.read()


def _clean_columns(df):
    df = df.copy()

    df.columns = [
        str(column)
        .replace("\ufeff", "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        for column in df.columns
    ]

    return df


def _read_csv_bytes(data):
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            df = pd.read_csv(
                io.BytesIO(data),
                encoding=encoding,
                low_memory=False,
            )

            if not df.empty:
                return _clean_columns(df)

        except Exception:
            continue

    return pd.DataFrame()


def _find_column(df, keywords):
    for column in df.columns:
        lowered = str(column).lower()

        for keyword in keywords:
            if keyword.lower() in lowered:
                return column

    return None


def _parse_timestamp(value):
    if value is None or pd.isna(value):
        return pd.NaT

    return pd.to_datetime(
        value,
        errors="coerce",
        utc=True,
    ).tz_localize(None)


def _duration_minutes(value):
    value = safe_float(value, 0.0)

    if value <= 0:
        return 0.0

    # Strava activity export commonly stores elapsed/moving time
    # as seconds.
    if value > 300:
        return round(value / 60.0, 2)

    return round(value, 2)


def _distance_km(value):
    value = safe_float(value, 0.0)

    if value <= 0:
        return 0.0

    return round(value, 3)


def _normalise_strava_activities(df):
    if df.empty:
        return pd.DataFrame()

    date_column = _find_column(
        df,
        [
            "activity_date",
            "start_date",
            "date",
        ],
    )

    duration_column = _find_column(
        df,
        [
            "moving_time",
            "elapsed_time",
            "duration",
        ],
    )

    heart_column = _find_column(
        df,
        [
            "average_heart_rate",
            "average_heartrate",
            "avg_heart_rate",
            "avg_hr",
        ],
    )

    distance_column = _find_column(
        df,
        [
            "distance",
        ],
    )

    calories_column = _find_column(
        df,
        [
            "calories",
        ],
    )

    ascent_column = _find_column(
        df,
        [
            "elevation_gain",
            "total_elevation_gain",
            "elevation",
            "ascent",
        ],
    )

    speed_column = _find_column(
        df,
        [
            "average_speed",
            "avg_speed",
        ],
    )

    relative_effort_column = _find_column(
        df,
        [
            "relative_effort",
            "suffer_score",
        ],
    )

    rows = []

    for _, source_row in df.iterrows():

        timestamp = (
            _parse_timestamp(source_row.get(date_column))
            if date_column
            else pd.Timestamp.now()
        )

        if pd.isna(timestamp):
            timestamp = pd.Timestamp.now()

        heart_rate = (
            safe_float(
                source_row.get(heart_column),
                120.0,
            )
            if heart_column
            else 120.0
        )

        duration_minutes = (
            _duration_minutes(
                source_row.get(duration_column)
            )
            if duration_column
            else 30.0
        )

        if duration_minutes <= 0:
            duration_minutes = 30.0

        distance = (
            _distance_km(
                source_row.get(distance_column)
            )
            if distance_column
            else 0.0
        )

        calories = (
            safe_float(
                source_row.get(calories_column),
                0.0,
            )
            if calories_column
            else 0.0
        )

        total_ascent = (
            safe_float(
                source_row.get(ascent_column),
                0.0,
            )
            if ascent_column
            else 0.0
        )

        avg_speed = (
            safe_float(
                source_row.get(speed_column),
                0.0,
            )
            if speed_column
            else 0.0
        )

        relative_effort = (
            safe_float(
                source_row.get(relative_effort_column),
                0.0,
            )
            if relative_effort_column
            else 0.0
        )

        # Prefer Strava Relative Effort when available.
        if relative_effort > 0:
            training_load = round(relative_effort, 2)
        else:
            training_load = round(
                (heart_rate * duration_minutes) / 100.0,
                2,
            )

        # Strava does not normally provide sleep/recovery information
        # in its activity export, so QUTwin uses neutral defaults here.
        sleep_hours = 7.0

        recovery_time = max(
            1.0,
            round(
                sleep_hours
                + 2
                - (training_load / 100.0),
                2,
            ),
        )

        rows.append(
            {
                "timestamp": timestamp,
                "heart_rate": heart_rate,
                "sleep_hours": sleep_hours,
                "training_load": training_load,
                "recovery_time": recovery_time,
                "hydration_level": "Medium",
                "temperature": 25.0,
                "humidity": 60.0,
                "previous_injury": 0,
                "distance": distance,
                "avg_speed": avg_speed,
                "calories": calories,
                "total_ascent": total_ascent,
                "duration_minutes": duration_minutes,
            }
        )

    return pd.DataFrame(rows)


def parse_strava_csv(uploaded_file):
    """
    Parse Strava activities.csv or a compatible Strava activity CSV.
    """

    data = _get_bytes(uploaded_file)
    raw_df = _read_csv_bytes(data)

    if raw_df.empty:
        return pd.DataFrame(), {}

    model_ready = _normalise_strava_activities(raw_df)

    return model_ready, {
        "activities": raw_df,
    }


def parse_strava_zip(uploaded_file):
    """
    Parse a Strava bulk account export.

    The primary source used here is activities.csv. Original FIT/TCX/GPX
    activity files inside the archive can be parsed individually later.
    """

    data = _get_bytes(uploaded_file)

    activities_df = pd.DataFrame()
    raw_preview = {}

    with zipfile.ZipFile(
        io.BytesIO(data),
        "r",
    ) as archive:

        for filename in archive.namelist():

            clean_name = filename.lower().replace("\\", "/")

            if clean_name.endswith("activities.csv"):
                try:
                    file_data = archive.read(filename)

                    activities_df = _read_csv_bytes(
                        file_data
                    )

                    if not activities_df.empty:
                        raw_preview["activities"] = (
                            activities_df.head(100)
                        )

                    break

                except Exception:
                    continue

    if activities_df.empty:
        return pd.DataFrame(), raw_preview

    model_ready = _normalise_strava_activities(
        activities_df
    )

    return model_ready, raw_preview