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
    """
    Samsung Health CSV exports can contain slightly different structures.
    Try a few safe CSV-reading strategies.
    """

    attempts = [
        {"encoding": "utf-8-sig"},
        {"encoding": "utf-8"},
        {"encoding": "latin1"},
    ]

    for options in attempts:
        try:
            df = pd.read_csv(
                io.BytesIO(data),
                low_memory=False,
                **options,
            )

            if not df.empty:
                return _clean_columns(df)

        except Exception:
            continue

    # Some exports may contain an extra line before the real header.
    for options in attempts:
        try:
            df = pd.read_csv(
                io.BytesIO(data),
                skiprows=1,
                low_memory=False,
                **options,
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

    try:
        numeric = float(value)

        # Milliseconds since Unix epoch
        if numeric > 1_000_000_000_000:
            return pd.to_datetime(numeric, unit="ms", errors="coerce")

        # Seconds since Unix epoch
        if numeric > 1_000_000_000:
            return pd.to_datetime(numeric, unit="s", errors="coerce")

    except Exception:
        pass

    return pd.to_datetime(value, errors="coerce")


def _duration_minutes(value):
    value = safe_float(value, 0.0)

    if value <= 0:
        return 0.0

    # Common millisecond duration
    if value > 100000:
        return round(value / 60000.0, 2)

    # Common seconds duration
    if value > 1000:
        return round(value / 60.0, 2)

    # Likely hours
    if value <= 24:
        return round(value * 60.0, 2)

    # Otherwise treat as minutes
    return round(value, 2)


def _detect_category(filename, df):
    name = filename.lower()
    columns = " ".join(df.columns).lower()

    if "exercise" in name or "workout" in name:
        return "exercise"

    if (
        "heart_rate" in name
        or "heartrate" in name
        or "heart_rate" in columns
    ):
        return "heart_rate"

    if "sleep" in name:
        return "sleep"

    if "water" in name or "hydration" in name:
        return "water"

    if "temperature" in name:
        return "temperature"

    if (
        "step" in name
        or "activity" in name
        or "calorie" in name
    ):
        return "activity"

    return "other"


def _latest_numeric(frames, keywords, default):
    for df in reversed(frames):
        if df.empty:
            continue

        column = _find_column(df, keywords)

        if column:
            values = pd.to_numeric(
                df[column],
                errors="coerce",
            ).dropna()

            if not values.empty:
                return float(values.iloc[-1])

    return default


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
                "mean_heart_rate",
                "average_heart_rate",
                "avg_heart_rate",
                "heart_rate_mean",
            ],
        )

        if column:
            numeric = pd.to_numeric(
                df[column],
                errors="coerce",
            ).dropna()

            values.extend(numeric.tolist())

    if values:
        return round(float(pd.Series(values).mean()), 2)

    return 120.0


def _sleep_hours(frames):
    durations = []

    for df in frames:
        if df.empty:
            continue

        duration_column = _find_column(
            df,
            [
                "sleep_duration",
                "duration",
            ],
        )

        if duration_column:
            for value in df[duration_column].dropna():
                minutes = _duration_minutes(value)

                if 60 <= minutes <= 1000:
                    durations.append(minutes)

    if durations:
        return round(float(pd.Series(durations).iloc[-1]) / 60.0, 2)

    # Try start/end timestamps
    for df in frames:
        start_column = _find_column(
            df,
            ["start_time", "start"],
        )
        end_column = _find_column(
            df,
            ["end_time", "end"],
        )

        if start_column and end_column and not df.empty:
            last = df.iloc[-1]

            start = _parse_timestamp(last.get(start_column))
            end = _parse_timestamp(last.get(end_column))

            if pd.notna(start) and pd.notna(end):
                hours = (end - start).total_seconds() / 3600.0

                if 0 < hours <= 24:
                    return round(hours, 2)

    return 7.0


def _hydration_level(frames):
    amount = _latest_numeric(
        frames,
        [
            "amount",
            "water",
            "volume",
            "intake",
        ],
        1500.0,
    )

    if amount < 1000:
        return "Low"

    if amount < 2500:
        return "Medium"

    return "High"


def _build_from_exercise(
    exercise_frames,
    heart_frames,
    sleep_frames,
    water_frames,
    temperature_frames,
):
    rows = []

    heart_rate_default = _average_heart_rate(heart_frames)
    sleep_hours = _sleep_hours(sleep_frames)
    hydration_level = _hydration_level(water_frames)

    temperature_default = _latest_numeric(
        temperature_frames,
        [
            "temperature",
            "body_temperature",
        ],
        25.0,
    )

    for df in exercise_frames:
        if df.empty:
            continue

        timestamp_column = _find_column(
            df,
            [
                "start_time",
                "start_timestamp",
                "start",
                "create_time",
                "created_time",
            ],
        )

        duration_column = _find_column(
            df,
            [
                "duration",
                "exercise_duration",
            ],
        )

        heart_column = _find_column(
            df,
            [
                "mean_heart_rate",
                "average_heart_rate",
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
                "calorie",
                "calories",
                "energy",
            ],
        )

        speed_column = _find_column(
            df,
            [
                "mean_speed",
                "average_speed",
                "avg_speed",
                "speed",
            ],
        )

        ascent_column = _find_column(
            df,
            [
                "elevation_gain",
                "total_ascent",
                "ascent",
            ],
        )

        temperature_column = _find_column(
            df,
            [
                "temperature",
                "body_temperature",
            ],
        )

        for _, source_row in df.iterrows():

            timestamp = (
                _parse_timestamp(source_row.get(timestamp_column))
                if timestamp_column
                else pd.Timestamp.now()
            )

            if pd.isna(timestamp):
                timestamp = pd.Timestamp.now()

            heart_rate = (
                safe_float(
                    source_row.get(heart_column),
                    heart_rate_default,
                )
                if heart_column
                else heart_rate_default
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
                safe_float(
                    source_row.get(distance_column),
                    0.0,
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

            avg_speed = (
                safe_float(
                    source_row.get(speed_column),
                    0.0,
                )
                if speed_column
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

            temperature = (
                safe_float(
                    source_row.get(temperature_column),
                    temperature_default,
                )
                if temperature_column
                else temperature_default
            )

            training_load = round(
                (heart_rate * duration_minutes) / 100.0,
                2,
            )

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
                    "hydration_level": hydration_level,
                    "temperature": temperature,
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
    water_frames,
    temperature_frames,
):
    """
    Create one QUTwin state when the Samsung export contains health
    measurements but no exercise session.
    """

    if (
        not heart_frames
        and not sleep_frames
        and not water_frames
        and not temperature_frames
    ):
        return pd.DataFrame()

    heart_rate = _average_heart_rate(heart_frames)
    sleep_hours = _sleep_hours(sleep_frames)
    hydration_level = _hydration_level(water_frames)

    temperature = _latest_numeric(
        temperature_frames,
        [
            "temperature",
            "body_temperature",
        ],
        25.0,
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
                "hydration_level": hydration_level,
                "temperature": temperature,
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
    exercise_frames = frames.get("exercise", [])
    heart_frames = frames.get("heart_rate", [])
    sleep_frames = frames.get("sleep", [])
    water_frames = frames.get("water", [])
    temperature_frames = frames.get("temperature", [])

    if exercise_frames:
        model_ready = _build_from_exercise(
            exercise_frames=exercise_frames,
            heart_frames=heart_frames,
            sleep_frames=sleep_frames,
            water_frames=water_frames,
            temperature_frames=temperature_frames,
        )

        if not model_ready.empty:
            return model_ready

    return _build_health_snapshot(
        heart_frames=heart_frames,
        sleep_frames=sleep_frames,
        water_frames=water_frames,
        temperature_frames=temperature_frames,
    )


def parse_samsung_health_csv(uploaded_file):
    data = _get_bytes(uploaded_file)
    df = _read_csv_bytes(data)

    if df.empty:
        return pd.DataFrame(), {}

    category = _detect_category(
        uploaded_file.name,
        df,
    )

    frames = {
        "exercise": [],
        "heart_rate": [],
        "sleep": [],
        "water": [],
        "temperature": [],
        "activity": [],
        "other": [],
    }

    frames.setdefault(category, []).append(df)

    model_ready = _build_model_ready(frames)

    return model_ready, {
        category: df,
    }


def parse_samsung_health_zip(uploaded_file):
    data = _get_bytes(uploaded_file)

    frames = {
        "exercise": [],
        "heart_rate": [],
        "sleep": [],
        "water": [],
        "temperature": [],
        "activity": [],
        "other": [],
    }

    raw_preview = {}

    with zipfile.ZipFile(
        io.BytesIO(data),
        "r",
    ) as archive:

        for filename in archive.namelist():

            if not filename.lower().endswith(".csv"):
                continue

            try:
                file_data = archive.read(filename)
                df = _read_csv_bytes(file_data)

                if df.empty:
                    continue

                category = _detect_category(
                    filename,
                    df,
                )

                frames.setdefault(
                    category,
                    [],
                ).append(df)

                # Keep preview manageable.
                raw_preview[filename] = df.head(100)

            except Exception:
                continue

    model_ready = _build_model_ready(frames)

    return model_ready, raw_preview