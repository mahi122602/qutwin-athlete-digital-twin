from ingestion.auto_detector import detect_file_type
from ingestion.csv_parser import parse_csv
from ingestion.excel_parser import parse_excel
from ingestion.garmin_zip_parser import parse_garmin_zip
from preprocessing.feature_engineering import (
    normalise_garmin_activity_csv,
    normalise_generic_input,
)


def load_uploaded_file(uploaded_file):
    file_type = detect_file_type(uploaded_file.name)

    if file_type == "zip":
        model_ready, raw_preview = parse_garmin_zip(uploaded_file)
        return model_ready, raw_preview, "Garmin ZIP"

    if file_type == "csv":
        raw_df = parse_csv(uploaded_file)

        if "Avg HR" in raw_df.columns or "Laps" in raw_df.columns:
            model_ready = normalise_garmin_activity_csv(raw_df)
        else:
            model_ready = normalise_generic_input(raw_df)

        return model_ready, {"csv": raw_df}, "CSV"

    if file_type == "excel":
        raw_df = parse_excel(uploaded_file)
        model_ready = normalise_generic_input(raw_df)
        return model_ready, {"excel": raw_df}, "Excel"

    raise ValueError("Unsupported file type. Please upload ZIP, CSV, Excel, or Garmin export.")