import io
import xml.etree.ElementTree as ET

import pandas as pd

from preprocessing.feature_engineering import safe_float


def _get_bytes(uploaded_file):
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()

    uploaded_file.seek(0)
    return uploaded_file.read()


def _parse_date(value):
    if not value:
        return pd.NaT

    return pd.to_datetime(
        value,
        errors="coerce",
    )


def _hours_between(start, end):
    start = _parse_date(start)
    end = _parse_date(end)

    if pd.isna(start) or pd.isna(end):
        return 0.0

    seconds = (end - start).total_seconds()

    if seconds <= 0:
        return 0.0

    return round(seconds / 3600.0, 2)


def _water_ml(value, unit):
    value = safe_float(value, 0.0)

    unit = str(unit or "").lower()

    if unit in {"l", "liter", "litre"}:
        return value * 1000.0

    if unit in {"fl_oz_us", "oz"}:
        return value * 29.5735

    return value


def _distance_km(value, unit):
    value = safe_float(value, 0.0)

    unit = str(unit or "").lower()

    if unit in {"mi", "mile", "miles"}:
        return round(value * 1.60934, 3)

    if unit in {"m", "meter", "meters"}:
        return round(value / 1000.0, 3)

    return round(value, 3)


def _duration_minutes(value, unit):
    value = safe_float(value, 0.0)

    unit = str(unit or "").lower()

    if unit in {"s", "sec", "second", "seconds"}:
        return round(value / 60.0, 2)

    if unit in {"h", "hr", "hour", "hours"}:
        return round(value * 60.0, 2)

    return round(value, 2)


def _hydration_label(total_ml):
    if total_ml < 1000:
        return "Low"

    if total_ml < 2500:
        return "Medium"

    return "High"


def parse_apple_health_xml(uploaded_file):
    """
    Parse a standard Apple Health export.xml file and convert it
    into QUTwin model-ready features.
    """

    data = _get_bytes(uploaded_file)

    workouts = []
    heart_records = []
    sleep_records = []
    water_records = []
    temperature_records = []

    try:
        context = ET.iterparse(
            io.BytesIO(data),
            events=("end",),
        )

        for _, element in context:

            tag = element.tag.split("}")[-1]

            # -------------------------------------------------
            # WORKOUTS
            # -------------------------------------------------
            if tag == "Workout":
                attrs = element.attrib

                workouts.append(
                    {
                        "timestamp": attrs.get(
                            "startDate"
                        ),
                        "end_date": attrs.get(
                            "endDate"
                        ),
                        "activity_type": attrs.get(
                            "workoutActivityType"
                        ),
                        "duration": attrs.get(
                            "duration"
                        ),
                        "duration_unit": attrs.get(
                            "durationUnit",
                            "min",
                        ),
                        "distance": attrs.get(
                            "totalDistance"
                        ),
                        "distance_unit": attrs.get(
                            "totalDistanceUnit",
                            "km",
                        ),
                        "calories": attrs.get(
                            "totalEnergyBurned"
                        ),
                    }
                )

            # -------------------------------------------------
            # HEALTH RECORDS
            # -------------------------------------------------
            elif tag == "Record":
                attrs = element.attrib

                record_type = str(
                    attrs.get(
                        "type",
                        "",
                    )
                )

                record_type_lower = (
                    record_type.lower()
                )

                # Heart rate
                if "heartrate" in record_type_lower:
                    heart_records.append(
                        {
                            "timestamp": attrs.get(
                                "startDate"
                            ),
                            "value": attrs.get(
                                "value"
                            ),
                        }
                    )

                # Sleep
                elif "sleepanalysis" in record_type_lower:
                    value = str(
                        attrs.get(
                            "value",
                            "",
                        )
                    ).lower()

                    if (
                        "asleep" in value
                        and "inbed" not in value
                    ):
                        sleep_records.append(
                            {
                                "start": attrs.get(
                                    "startDate"
                                ),
                                "end": attrs.get(
                                    "endDate"
                                ),
                                "value": attrs.get(
                                    "value"
                                ),
                            }
                        )

                # Water / hydration
                elif (
                    "dietarywater"
                    in record_type_lower
                ):
                    water_records.append(
                        {
                            "timestamp": attrs.get(
                                "startDate"
                            ),
                            "value": attrs.get(
                                "value"
                            ),
                            "unit": attrs.get(
                                "unit"
                            ),
                        }
                    )

                # Body temperature
                elif (
                    "bodytemperature"
                    in record_type_lower
                    or "basalbodytemperature"
                    in record_type_lower
                ):
                    temperature_records.append(
                        {
                            "timestamp": attrs.get(
                                "startDate"
                            ),
                            "value": attrs.get(
                                "value"
                            ),
                            "unit": attrs.get(
                                "unit"
                            ),
                        }
                    )

            element.clear()

    except ET.ParseError as exc:
        raise ValueError(
            f"Apple Health XML could not be parsed: {exc}"
        )

    # ---------------------------------------------------------
    # RAW DATAFRAMES
    # ---------------------------------------------------------
    workouts_df = pd.DataFrame(
        workouts
    )

    heart_df = pd.DataFrame(
        heart_records
    )

    sleep_df = pd.DataFrame(
        sleep_records
    )

    water_df = pd.DataFrame(
        water_records
    )

    temperature_df = pd.DataFrame(
        temperature_records
    )

    raw_preview = {
        "workouts": workouts_df.head(100),
        "heart_rate": heart_df.head(100),
        "sleep": sleep_df.head(100),
        "water": water_df.head(100),
        "temperature": temperature_df.head(100),
    }

    # ---------------------------------------------------------
    # HEART RATE DEFAULT
    # ---------------------------------------------------------
    heart_rate_default = 120.0

    if not heart_df.empty:
        values = pd.to_numeric(
            heart_df["value"],
            errors="coerce",
        ).dropna()

        values = values[
            (values >= 30)
            & (values <= 240)
        ]

        if not values.empty:
            heart_rate_default = round(
                float(values.mean()),
                2,
            )

    # ---------------------------------------------------------
    # SLEEP HOURS
    # ---------------------------------------------------------
    sleep_hours = 7.0

    if not sleep_df.empty:
        sleep_df = sleep_df.copy()

        sleep_df["hours"] = sleep_df.apply(
            lambda row: _hours_between(
                row.get("start"),
                row.get("end"),
            ),
            axis=1,
        )

        valid_sleep = sleep_df[
            sleep_df["hours"] > 0
        ]

        if not valid_sleep.empty:
            valid_sleep["date"] = pd.to_datetime(
                valid_sleep["start"],
                errors="coerce",
            ).dt.date

            daily_sleep = (
                valid_sleep.groupby("date")[
                    "hours"
                ]
                .sum()
            )

            if not daily_sleep.empty:
                sleep_hours = round(
                    float(
                        daily_sleep.iloc[-1]
                    ),
                    2,
                )

                sleep_hours = min(
                    sleep_hours,
                    14.0,
                )

    # ---------------------------------------------------------
    # HYDRATION
    # ---------------------------------------------------------
    total_water_ml = 1500.0

    if not water_df.empty:
        water_df = water_df.copy()

        water_df["ml"] = water_df.apply(
            lambda row: _water_ml(
                row.get("value"),
                row.get("unit"),
            ),
            axis=1,
        )

        total_water_ml = float(
            water_df["ml"].sum()
        )

    hydration_level = (
        _hydration_label(
            total_water_ml
        )
    )

    # ---------------------------------------------------------
    # TEMPERATURE
    # ---------------------------------------------------------
    temperature = 25.0

    if not temperature_df.empty:
        values = pd.to_numeric(
            temperature_df["value"],
            errors="coerce",
        ).dropna()

        if not values.empty:
            temperature = float(
                values.iloc[-1]
            )

    # ---------------------------------------------------------
    # BUILD QUTWIN STATES FROM WORKOUTS
    # ---------------------------------------------------------
    rows = []

    if not workouts_df.empty:

        for _, workout in workouts_df.iterrows():

            timestamp = _parse_date(
                workout.get(
                    "timestamp"
                )
            )

            if pd.isna(timestamp):
                timestamp = pd.Timestamp.now()

            duration_minutes = (
                _duration_minutes(
                    workout.get(
                        "duration"
                    ),
                    workout.get(
                        "duration_unit"
                    ),
                )
            )

            if duration_minutes <= 0:
                duration_minutes = 30.0

            distance = _distance_km(
                workout.get(
                    "distance"
                ),
                workout.get(
                    "distance_unit"
                ),
            )

            calories = safe_float(
                workout.get(
                    "calories"
                ),
                0.0,
            )

            # Use heart-rate measurements recorded near the workout
            # when they are available.
            heart_rate = heart_rate_default

            if not heart_df.empty:
                temporary = heart_df.copy()

                temporary[
                    "parsed_timestamp"
                ] = pd.to_datetime(
                    temporary["timestamp"],
                    errors="coerce",
                )

                workout_end = _parse_date(
                    workout.get(
                        "end_date"
                    )
                )

                if pd.notna(workout_end):
                    matching = temporary[
                        (
                            temporary[
                                "parsed_timestamp"
                            ]
                            >= timestamp
                        )
                        & (
                            temporary[
                                "parsed_timestamp"
                            ]
                            <= workout_end
                        )
                    ]

                    if not matching.empty:
                        values = pd.to_numeric(
                            matching["value"],
                            errors="coerce",
                        ).dropna()

                        values = values[
                            (values >= 30)
                            & (values <= 240)
                        ]

                        if not values.empty:
                            heart_rate = round(
                                float(
                                    values.mean()
                                ),
                                2,
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

            avg_speed = 0.0

            if (
                distance > 0
                and duration_minutes > 0
            ):
                avg_speed = round(
                    distance
                    / (
                        duration_minutes
                        / 60.0
                    ),
                    2,
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
                    "total_ascent": 0.0,
                    "duration_minutes": duration_minutes,
                }
            )

    # ---------------------------------------------------------
    # HEALTH-ONLY SNAPSHOT
    # ---------------------------------------------------------
    if not rows and (
        not heart_df.empty
        or not sleep_df.empty
        or not water_df.empty
        or not temperature_df.empty
    ):

        training_load = 30.0

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
                "timestamp": pd.Timestamp.now(),
                "heart_rate": heart_rate_default,
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
        )

    model_ready = pd.DataFrame(
        rows
    )

    return (
        model_ready,
        raw_preview,
    )


def parse_apple_health_zip(uploaded_file):
    """
    Find Apple's export.xml inside an Apple Health ZIP export
    and parse it through the standard XML parser.
    """

    import zipfile

    data = _get_bytes(
        uploaded_file
    )

    with zipfile.ZipFile(
        io.BytesIO(data),
        "r",
    ) as archive:

        export_filename = None

        for filename in archive.namelist():

            lower = (
                filename
                .lower()
                .replace("\\", "/")
            )

            if lower.endswith(
                "export.xml"
            ):
                export_filename = filename
                break

        if export_filename is None:
            return (
                pd.DataFrame(),
                {},
            )

        export_data = archive.read(
            export_filename
        )

    class AppleXMLFile:
        name = "export.xml"

        def getvalue(self):
            return export_data

        def seek(self, *_):
            return None

    return parse_apple_health_xml(
        AppleXMLFile()
    )