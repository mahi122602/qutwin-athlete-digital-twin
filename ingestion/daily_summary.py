"""Validate daily observations without deriving prediction inputs."""
import hashlib
import json
import pandas as pd


def prepare_daily_summary(frame):
    if 'day_time' not in frame.columns:
        raise ValueError('Daily summary export needs a day_time column.')
    dates = pd.to_datetime(frame['day_time'], errors='coerce')
    if dates.isna().any():
        raise ValueError('One or more summary dates are invalid. No records were saved.')
    result = frame.copy()
    result['timestamp'] = dates
    return result


def summary_records(frame):
    checked = prepare_daily_summary(frame)
    # JSON serialization converts pandas missing values to null.
    raw = json.loads(checked.drop(columns=['timestamp']).to_json(orient='records', date_format='iso'))
    records = []
    for date_value, payload in zip(checked['timestamp'], raw):
        identifier = payload.get('datauuid')
        key = str(identifier) if identifier else hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        records.append((key, date_value.date(), payload))
    return records
