import os


def detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]

    if ext == ".zip":
        return "zip"
    if ext == ".csv":
        return "csv"
    if ext in [".xlsx", ".xls"]:
        return "excel"
    if ext == ".fit":
        return "fit"

    return "unknown"