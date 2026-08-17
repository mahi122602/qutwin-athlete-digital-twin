import pandas as pd

from ingestion.auto_detector import detect_upload_source
from ingestion.csv_parser import parse_csv
from ingestion.excel_parser import parse_excel
from ingestion.garmin_zip_parser import parse_garmin_zip

from ingestion.samsung_health_parser import (
    parse_samsung_health_csv,
    parse_samsung_health_zip,
)

from ingestion.strava_parser import (
    parse_strava_csv,
    parse_strava_zip,
)

from ingestion.fitbit_parser import (
    parse_fitbit_csv,
    parse_fitbit_json,
    parse_fitbit_zip,
)

from ingestion.apple_health_parser import (
    parse_apple_health_xml,
    parse_apple_health_zip,
)

from preprocessing.feature_engineering import (
    normalise_garmin_activity_csv,
    normalise_generic_input,
)


def load_uploaded_file(uploaded_file):
    """
    Detect the uploaded athlete-data source and file type,
    then convert supported data into the standard QUTwin
    model-ready format.

    Currently connected:
        - Garmin
        - Samsung Health
        - Strava
        - Fitbit
        - Apple Health

    Detection already recognises additional sources such as:
        - Polar
        - WHOOP
        - COROS

    Those parsers will be connected separately.

    Returns:
        model_ready_df : pandas.DataFrame
        raw_preview    : dict
        detection      : dict
    """

    # =========================================================
    # 1. DETECT SOURCE + FILE TYPE
    # =========================================================
    detection = detect_upload_source(uploaded_file)

    file_type = detection.get(
        "file_type",
        "unknown",
    )

    source = detection.get(
        "source",
        "Unknown",
    )

    # Detection may read from the uploaded file.
    # Reset before passing it to a parser.
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    # =========================================================
    # 2. ZIP FILES
    # =========================================================
    if file_type == "zip":

        # -----------------------------------------------------
        # Garmin
        # -----------------------------------------------------
        if source == "Garmin":
            model_ready, raw_preview = parse_garmin_zip(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # -----------------------------------------------------
        # Samsung Health
        # -----------------------------------------------------
        if source == "Samsung Health":
            model_ready, raw_preview = parse_samsung_health_zip(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # -----------------------------------------------------
        # Strava
        # -----------------------------------------------------
        if source == "Strava":
            model_ready, raw_preview = parse_strava_zip(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # -----------------------------------------------------
        # Fitbit
        # -----------------------------------------------------
        if source == "Fitbit":
            model_ready, raw_preview = parse_fitbit_zip(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # -----------------------------------------------------
        # Apple Health
        # -----------------------------------------------------
        if source == "Apple Health":
            model_ready, raw_preview = parse_apple_health_zip(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # ZIP detected, but parser not yet connected.
        return (
            pd.DataFrame(),
            {},
            detection,
        )

    # =========================================================
    # 3. CSV FILES
    # =========================================================
    if file_type == "csv":

        # -----------------------------------------------------
        # Samsung Health
        # -----------------------------------------------------
        if source == "Samsung Health":
            model_ready, raw_preview = parse_samsung_health_csv(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # -----------------------------------------------------
        # Strava
        # -----------------------------------------------------
        if source == "Strava":
            model_ready, raw_preview = parse_strava_csv(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # -----------------------------------------------------
        # Fitbit
        # -----------------------------------------------------
        if source == "Fitbit":
            model_ready, raw_preview = parse_fitbit_csv(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # -----------------------------------------------------
        # Garmin or Generic CSV
        # -----------------------------------------------------
        raw_df = parse_csv(
            uploaded_file
        )

        if (
            source == "Garmin"
            or "Avg HR" in raw_df.columns
            or "Laps" in raw_df.columns
        ):
            model_ready = normalise_garmin_activity_csv(
                raw_df
            )

        else:
            try:
                model_ready = normalise_generic_input(
                    raw_df
                )

            except Exception:
                model_ready = pd.DataFrame()

        return (
            model_ready,
            {
                "csv": raw_df,
            },
            detection,
        )

    # =========================================================
    # 4. JSON FILES
    # =========================================================
    if file_type == "json":

        # -----------------------------------------------------
        # Fitbit
        # -----------------------------------------------------
        if source == "Fitbit":
            model_ready, raw_preview = parse_fitbit_json(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # Other JSON parsers will be added later.
        return (
            pd.DataFrame(),
            {},
            detection,
        )

    # =========================================================
    # 5. EXCEL FILES
    # =========================================================
    if file_type == "excel":

        raw_df = parse_excel(
            uploaded_file
        )

        try:
            model_ready = normalise_generic_input(
                raw_df
            )

        except Exception:
            model_ready = pd.DataFrame()

        return (
            model_ready,
            {
                "excel": raw_df,
            },
            detection,
        )

    # =========================================================
    # 6. APPLE HEALTH XML
    # =========================================================
    if file_type == "xml":

        if source == "Apple Health":
            model_ready, raw_preview = parse_apple_health_xml(
                uploaded_file
            )

            return (
                model_ready,
                raw_preview,
                detection,
            )

        # Other XML sources not connected yet.
        return (
            pd.DataFrame(),
            {},
            detection,
        )

    # =========================================================
    # 7. FIT FILES
    # =========================================================
    if file_type == "fit":

        # FIT source detection already works.
        # Parsing will be connected for:
        # Garmin / Strava / Polar / COROS.
        return (
            pd.DataFrame(),
            {},
            detection,
        )

    # =========================================================
    # 8. TCX FILES
    # =========================================================
    if file_type == "tcx":

        # TCX parser will later support:
        # Garmin / Strava / Polar / COROS.
        return (
            pd.DataFrame(),
            {},
            detection,
        )

    # =========================================================
    # 9. GPX FILES
    # =========================================================
    if file_type == "gpx":

        # GPX parser will later support:
        # Garmin / Strava / Polar / COROS.
        return (
            pd.DataFrame(),
            {},
            detection,
        )

    # =========================================================
    # 10. UNSUPPORTED FILE TYPE
    # =========================================================
    raise ValueError(
        "Unsupported file type. "
        "Please upload ZIP, CSV, Excel, FIT, "
        "TCX, GPX, XML, or JSON."
    )