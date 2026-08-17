import io
import json
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


def _read_json_bytes(data):
    try:
        payload = json.loads(
            data.decode("utf-8", errors="ignore")
        )
    except Exception:
        return pd.DataFrame()

    try:
        if isinstance(payload, list):
            df = pd.json_normalize(payload)

        elif isinstance(payload, dict):
            list_value = None

            for value in payload.values():
                if isinstance(value, list):
                    list_value = value
                    break

            if list_value is not None:
                df = pd.json_normalize(list_value)
            else:
                df = pd.json_normalize(payload)

        else:
            return pd.DataFrame()

        return _clean_columns(df)

    except Exception:
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
    )


def _duration_minutes(value):
    value = safe_float(value, 0.0)

    if value <= 0:
        return 0.0

    # Milliseconds
    if value > 100000:
        return round(value / 60000.0, 2)

    # Seconds
    if value > 1000:
        return round(value / 60.0, 2)

    return round(value, 2)


def _detect_category(filename):
    name = filename.lower()

    if (
        "heart" in name
        or "heartrate" in name
        or "heart_rate" in name
    ):
        return "heart_rate"

    if "sleep" in name:
        return "sleep"

    if (
        "exercise" in name
        or "activity" in name
        or "activities" in name
        or "distance" in name
        or "steps" in name
        or "calories" in name
    ):
        return "activity"

    if "spo2" in name or "oxygen" in name:
        return "spo2"

    if "hrv" in name:
        return "hrv"

    return "other"


def _average_heart_rate(frames):
    values = []

    for df in frames:
        if df.empty:
            continue

        column = _find_column(
            df,
            [
                "heart_rate",
                "heartrate",
                "average_heart_rate",
                "average_heartrate",
                "bpm",
                "value",
            ],
        )

        if column:
            numeric = pd.to_numeric(
                df[column],
                errors="coerce",
            ).dropna()

            numeric = numeric[
                (numeric >= 30)
                & (numeric <= 240)
            ]

            values.extend(numeric.tolist())

    if values:
        return round(
            float(pd.Series(values).mean()),
            2,
        )

    return 120.0


def _sleep_hours(frames):
    for df in reversed(frames):
        if df.empty:
            continue

        minutes_column = _find_column(
            df,
            [
                "minutesasleep",
                "minutes_asleep",
                "minutes_sleep",
            ],
        )

        if minutes_column:
            values = pd.to_numeric(
                df[minutes_column],
                errors="coerce",
            ).dropna()

            if not values.empty:
                minutes = float(values.iloc[-1])

                if 0 < minutes <= 1440:
                    return round(minutes / 60.0, 2)

        duration_column = _find_column(
            df,
            [
                "duration",
                "sleep_duration",
            ],
        )

        if duration_column:
            values = pd.to_numeric(
                df[duration_column],
                errors="coerce",
            ).dropna()

            if not values.empty:
                minutes = _duration_minutes(
                    values.iloc[-1]
                )

                if 30 <= minutes <= 1440:
                    return round(
                        minutes / 60.0,
                        2,
                    )

    return 7.0


def _normalise_activity_frames(
    activity_frames,
    heart_frames,
    sleep_frames,
):
    rows = []

    heart_default = _average_heart_rate(
        heart_frames
    )

    sleep_hours = _sleep_hours(
        sleep_frames
    )

    for df in activity_frames:
        if df.empty:
            continue

        timestamp_column = _find_column(
            df,
            [
                "start_time",
                "starttime",
                "datetime",
                "date_time",
                "date",
                "activity_date",
            ],
        )

        duration_column = _find_column(
            df,
            [
                "duration",
                "active_duration",
                "minutes",
                "active_minutes",
            ],
        )

        heart_column = _find_column(
            df,
            [
                "average_heart_rate",
                "average_heartrate",
                "avg_heart_rate",
                "heart_rate",
            ],
        )

        distance_column = _find_column(
            df,
            ["distance"],
        )

        calories_column = _find_column(
            df,
            [
                "calories",
                "calories_out",
            ],
        )

        speed_column = _find_column(
            df,
            [
                "average_speed",
                "avg_speed",
                "speed",
            ],
        )

        ascent_column = _find_column(
            df,
            [
                "elevation",
                "elevation_gain",
                "floors",
                "ascent",
            ],
        )

        for _, source_row in df.iterrows():

            timestamp = (
                _parse_timestamp(
                    source_row.get(
                        timestamp_column
                    )
                )
                if timestamp_column
                else pd.Timestamp.now()
            )

            if pd.isna(timestamp):
                timestamp = pd.Timestamp.now()

            heart_rate = (
                safe_float(
                    source_row.get(
                        heart_column
                    ),
                    heart_default,
                )
                if heart_column
                else heart_default
            )

            duration_minutes = (
                _duration_minutes(
                    source_row.get(
                        duration_column
                    )
                )
                if duration_column
                else 30.0
            )

            if duration_minutes <= 0:
                duration_minutes = 30.0

            distance = (
                safe_float(
                    source_row.get(
                        distance_column
                    ),
                    0.0,
                )
                if distance_column
                else 0.0
            )

            calories = (
                safe_float(
                    source_row.get(
                        calories_column
                    ),
                    0.0,
                )
                if calories_column
                else 0.0
            )

            avg_speed = (
                safe_float(
                    source_row.get(
                        speed_column
                    ),
                    0.0,
                )
                if speed_column
                else 0.0
            )

            total_ascent = (
                safe_float(
                    source_row.get(
                        ascent_column
                    ),
                    0.0,
                )
                if ascent_column
                else 0.0
            )

            training_load = round(
                (
                    heart_rate
                    * duration_minutes
                )
                / 100.0,
                2,
            )

            recovery_time = max(
                1.0,
                round(
                    sleep_hours
                    + 2
                    - (
                        training_load
                        / 100.0
                    ),
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


def _build_health_snapshot(
    heart_frames,
    sleep_frames,
):
    if not heart_frames and not sleep_frames:
        return pd.DataFrame()

    heart_rate = _average_heart_rate(
        heart_frames
    )

    sleep_hours = _sleep_hours(
        sleep_frames
    )

    training_load = 30.0

    recovery_time = max(
        1.0,
        round(
            sleep_hours
            + 2
            - (training_load / 100.0),
            2,
        ),
    )

    return pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp.now(),
                "heart_rate": heart_rate,
                "sleep_hours": sleep_hours,
                "training_load": training_load,
                "recovery_time": recovery_time,
                "hydration_level": "Medium",
                "temperature": 25.0,
                "humidity": 60.0,
                "previous_injury": 0,
                "distance": 0.0,
                "avg_speed": 0.0,
                "calories": 0.0,
                "total_ascent": 0.0,
                "duration_minutes": 0.0,
            }
        ]
    )


def _build_model_ready(frames):
    activity_frames = frames.get(
        "activity",
        [],
    )

    heart_frames = frames.get(
        "heart_rate",
        [],
    )

    sleep_frames = frames.get(
        "sleep",
        [],
    )

    if activity_frames:
        model_ready = (
            _normalise_activity_frames(
                activity_frames,
                heart_frames,
                sleep_frames,
            )
        )

        if not model_ready.empty:
            return model_ready

    return _build_health_snapshot(
        heart_frames,
        sleep_frames,
    )


def parse_fitbit_csv(uploaded_file):
    data = _get_bytes(uploaded_file)

    df = _read_csv_bytes(data)

    if df.empty:
        return pd.DataFrame(), {}

    category = _detect_category(
        uploaded_file.name
    )

    frames = {
        "activity": [],
        "heart_rate": [],
        "sleep": [],
        "spo2": [],
        "hrv": [],
        "other": [],
    }

    frames[category].append(df)

    model_ready = _build_model_ready(
        frames
    )

    return model_ready, {
        category: df,
    }


def parse_fitbit_json(uploaded_file):
    data = _get_bytes(uploaded_file)

    df = _read_json_bytes(data)

    if df.empty:
        return pd.DataFrame(), {}

    category = _detect_category(
        uploaded_file.name
    )

    frames = {
        "activity": [],
        "heart_rate": [],
        "sleep": [],
        "spo2": [],
        "hrv": [],
        "other": [],
    }

    frames[category].append(df)

    model_ready = _build_model_ready(
        frames
    )

    return model_ready, {
        category: df,
    }


def parse_fitbit_zip(uploaded_file):
    data = _get_bytes(uploaded_file)

    frames = {
        "activity": [],
        "heart_rate": [],
        "sleep": [],
        "spo2": [],
        "hrv": [],
        "other": [],
    }

    raw_preview = {}

    with zipfile.ZipFile(
        io.BytesIO(data),
        "r",
    ) as archive:

        for filename in archive.namelist():

            lower = filename.lower()

            try:
                if lower.endswith(".csv"):
                    file_data = archive.read(
                        filename
                    )

                    df = _read_csv_bytes(
                        file_data
                    )

                elif lower.endswith(".json"):
                    file_data = archive.read(
                        filename
                    )

                    df = _read_json_bytes(
                        file_data
                    )

                else:
                    continue

                if df.empty:
                    continue

                category = _detect_category(
                    filename
                )

                frames[
                    category
                ].append(df)

                raw_preview[
                    filename
                ] = df.head(100)

            except Exception:
                continue

    model_ready = _build_model_ready(
        frames
    )

    return model_ready, raw_preview