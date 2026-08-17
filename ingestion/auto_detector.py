import io
import json
import os
import zipfile
import xml.etree.ElementTree as ET

import pandas as pd


SUPPORTED_EXTENSIONS = {
    ".zip": "zip",
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".fit": "fit",
    ".tcx": "tcx",
    ".gpx": "gpx",
    ".xml": "xml",
    ".json": "json",
}


def detect_file_type(filename: str) -> str:
    """Detect the uploaded file type from its extension."""
    ext = os.path.splitext(filename.lower())[1]
    return SUPPORTED_EXTENSIONS.get(ext, "unknown")


def _result(
    file_type,
    source="Unknown",
    category="Unknown",
    confidence="Low",
    original_device_source=None,
):
    return {
        "file_type": file_type,
        "source": source,
        "category": category,
        "confidence": confidence,
        "original_device_source": original_device_source,
    }


def _filename_source(filename: str):
    """Use filename clues only when they are reasonably explicit."""
    name = filename.lower()

    clues = {
        "garmin": "Garmin",
        "strava": "Strava",
        "fitbit": "Fitbit",
        "samsung": "Samsung Health",
        "shealth": "Samsung Health",
        "apple_health": "Apple Health",
        "applehealth": "Apple Health",
        "polar": "Polar",
        "whoop": "WHOOP",
        "coros": "COROS",
    }

    for clue, source in clues.items():
        if clue in name:
            return source

    return None


def _detect_zip(uploaded_file):
    data = uploaded_file.getvalue()

    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        names = [name.lower() for name in archive.namelist()]
        joined = "\n".join(names)

        # Garmin account / Connect export
        if any(
            clue in joined
            for clue in (
                "di_connect",
                "summarizedactivities",
                "sleepdata",
                "hydrationlogfile",
                "udsfile",
                "traininghistory",
                "garmin",
            )
        ):
            return _result(
                "zip",
                "Garmin",
                "Health / Activity Export",
                "High",
                "Garmin",
            )

        # Samsung Health export
        if any(
            clue in joined
            for clue in (
                "com.samsung.health",
                "samsunghealth",
                "samsung_health",
                "shealth",
            )
        ):
            return _result(
                "zip",
                "Samsung Health",
                "Health Export",
                "High",
                "Samsung",
            )

        # WHOOP export
        if any(
            clue in joined
            for clue in (
                "physiological_cycles",
                "sleeps.csv",
                "workouts.csv",
                "journal_entries",
                "whoop",
            )
        ):
            return _result(
                "zip",
                "WHOOP",
                "Recovery / Activity Export",
                "High",
                "WHOOP",
            )

        # Apple Health export
        if any(
            clue in joined
            for clue in (
                "apple_health_export",
                "export.xml",
                "electrocardiograms",
            )
        ):
            return _result(
                "zip",
                "Apple Health",
                "Health Export",
                "High",
                "Apple",
            )

        # Strava bulk export
        if (
            "activities.csv" in joined
            and any("activities/" in name for name in names)
        ):
            return _result(
                "zip",
                "Strava",
                "Activity Export",
                "High",
            )

        # Generic filename clues inside ZIP
        for source_name in (
            "polar",
            "coros",
            "fitbit",
            "strava",
        ):
            if source_name in joined:
                source_map = {
                    "polar": "Polar",
                    "coros": "COROS",
                    "fitbit": "Fitbit",
                    "strava": "Strava",
                }
                return _result(
                    "zip",
                    source_map[source_name],
                    "Health / Activity Export",
                    "Medium",
                )

    return _result("zip")


def _detect_csv(uploaded_file):
    data = uploaded_file.getvalue()

    try:
        df = pd.read_csv(io.BytesIO(data), nrows=25)
    except Exception:
        return _result("csv")

    columns = [str(column).strip().lower() for column in df.columns]
    joined = " ".join(columns)

    # Garmin activity CSV
    if any(
        clue in joined
        for clue in (
            "avg hr",
            "average heart rate",
            "laps",
            "total ascent",
            "avg pace",
            "activity type",
        )
    ):
        return _result(
            "csv",
            "Garmin",
            "Activity",
            "High",
            "Garmin",
        )

    # WHOOP
    if (
        "recovery score" in joined
        or "strain" in joined
        or "hrv rmssd" in joined
        or "sleep performance" in joined
    ):
        return _result(
            "csv",
            "WHOOP",
            "Recovery / Activity",
            "High",
            "WHOOP",
        )

    # Samsung Health
    if any(
        clue in joined
        for clue in (
            "com.samsung.health",
            "deviceuuid",
            "datauuid",
            "pkg_name",
        )
    ):
        return _result(
            "csv",
            "Samsung Health",
            "Health / Activity",
            "High",
            "Samsung",
        )

    # Fitbit
    if any(
        clue in joined
        for clue in (
            "fitbit",
            "minutes asleep",
            "minutes awake",
            "sleep efficiency",
        )
    ):
        return _result(
            "csv",
            "Fitbit",
            "Health / Activity",
            "Medium",
            "Fitbit",
        )

    # Polar
    if (
        "polar" in joined
        or (
            "sport" in columns
            and "heart rate" in joined
            and "duration" in joined
        )
    ):
        return _result(
            "csv",
            "Polar",
            "Activity",
            "Medium",
            "Polar",
        )

    filename_source = _filename_source(uploaded_file.name)

    if filename_source:
        return _result(
            "csv",
            filename_source,
            "Health / Activity",
            "Medium",
        )

    return _result(
        "csv",
        "Unknown",
        "Generic Dataset",
        "Low",
    )


def _detect_json(uploaded_file):
    data = uploaded_file.getvalue()

    try:
        payload = json.loads(data.decode("utf-8", errors="ignore"))
        text = json.dumps(payload).lower()
    except Exception:
        return _result("json")

    if "garmin" in text:
        return _result(
            "json",
            "Garmin",
            "Health / Activity",
            "High",
            "Garmin",
        )

    if "fitbit" in text:
        return _result(
            "json",
            "Fitbit",
            "Health / Activity",
            "High",
            "Fitbit",
        )

    if "samsung" in text or "com.samsung.health" in text:
        return _result(
            "json",
            "Samsung Health",
            "Health / Activity",
            "High",
            "Samsung",
        )

    if "whoop" in text:
        return _result(
            "json",
            "WHOOP",
            "Health / Recovery",
            "High",
            "WHOOP",
        )

    return _result("json")


def _detect_xml(uploaded_file, file_type):
    data = uploaded_file.getvalue()

    try:
        root = ET.fromstring(data)
        sample = data[:10000].decode("utf-8", errors="ignore").lower()
        root_name = root.tag.lower()
    except Exception:
        return _result(file_type)

    if "healthdata" in root_name or "healthkit" in sample:
        return _result(
            file_type,
            "Apple Health",
            "Health Export",
            "High",
            "Apple",
        )

    if "trainingcenterdatabase" in sample:
        source = _filename_source(uploaded_file.name) or "Unknown"
        return _result(
            "tcx",
            source,
            "Activity",
            "Medium" if source != "Unknown" else "Low",
        )

    if "<gpx" in sample or "gpx" in root_name:
        source = _filename_source(uploaded_file.name) or "Unknown"
        return _result(
            "gpx",
            source,
            "Activity / GPS",
            "Medium" if source != "Unknown" else "Low",
        )

    return _result(file_type)


def _detect_fit(uploaded_file):
    """
    Detect the original FIT manufacturer when fitparse is available.

    A FIT file downloaded from Strava may still identify Garmin, Polar,
    COROS, etc. as the original device manufacturer.
    """
    try:
        from fitparse import FitFile

        data = uploaded_file.getvalue()
        fit_file = FitFile(io.BytesIO(data))

        manufacturer = None
        product = None

        for message in fit_file.get_messages("file_id"):
            for field in message:
                field_name = str(field.name).lower()

                if field_name == "manufacturer":
                    manufacturer = str(field.value)

                elif field_name in ("product", "garmin_product"):
                    product = str(field.value)

            break

        manufacturer_text = str(manufacturer or "").lower()

        mappings = {
            "garmin": "Garmin",
            "polar": "Polar",
            "coros": "COROS",
            "fitbit": "Fitbit",
            "apple": "Apple Health",
            "samsung": "Samsung Health",
        }

        for clue, source in mappings.items():
            if clue in manufacturer_text:
                return _result(
                    "fit",
                    source,
                    "Activity",
                    "High",
                    source,
                )

        if manufacturer:
            return _result(
                "fit",
                "Unknown",
                "Activity",
                "Medium",
                manufacturer,
            )

    except Exception:
        pass

    filename_source = _filename_source(uploaded_file.name)

    if filename_source:
        return _result(
            "fit",
            filename_source,
            "Activity",
            "Medium",
            filename_source,
        )

    return _result("fit", "Unknown", "Activity", "Low")


def detect_upload_source(uploaded_file):
    """
    Detect both file type and likely source.

    Returns:
        {
            "file_type": "...",
            "source": "...",
            "category": "...",
            "confidence": "...",
            "original_device_source": "..." or None
        }
    """
    file_type = detect_file_type(uploaded_file.name)

    if file_type == "zip":
        return _detect_zip(uploaded_file)

    if file_type == "csv":
        return _detect_csv(uploaded_file)

    if file_type == "fit":
        return _detect_fit(uploaded_file)

    if file_type in ("xml", "tcx", "gpx"):
        return _detect_xml(uploaded_file, file_type)

    if file_type == "json":
        return _detect_json(uploaded_file)

    if file_type == "excel":
        source = _filename_source(uploaded_file.name)

        return _result(
            "excel",
            source or "Unknown",
            "Generic Dataset",
            "Medium" if source else "Low",
        )

    return _result("unknown")