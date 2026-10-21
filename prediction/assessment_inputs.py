"""Validate optional, athlete-confirmed context for one selected activity."""
import math
import pandas as pd
from ingestion.adaptive_table import BOUNDS

FIELDS = ('sleep_hours', 'recovery_time', 'hydration_level', 'temperature', 'humidity', 'timestamp')


def validated_inputs(values):
    result = {}
    for key, value in (values or {}).items():
        if key not in FIELDS:
            raise ValueError('Unsupported assessment input: ' + str(key))
        if value is None or value == '':
            continue
        if key == 'hydration_level':
            value = str(value).strip().title()
            if value not in ('Low', 'Medium', 'High'):
                raise ValueError('Hydration must be Low, Medium or High, or left unknown.')
        elif key == 'timestamp':
            try:
                value = pd.Timestamp(value)
                if pd.isna(value) or value.tzinfo is None:
                    raise ValueError()
                value = value.tz_convert('UTC').isoformat()
            except (ValueError, TypeError):
                raise ValueError('Enter the actual activity time with its timezone offset, for example 2026-10-20T06:30:00+10:00.') from None
        else:
            try:
                value = float(value)
                lo, hi = BOUNDS[key]
                if not math.isfinite(value) or not lo <= value <= hi:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError(key.replace('_', ' ') + ' is outside the accepted measurement range.') from None
        result[key] = value
    return result


def with_context(record, values):
    context = validated_inputs(values)
    result = dict(record)
    result.update(context)
    if 'timestamp' in context:
        result['timestamp_origin'] = 'Athlete confirmed for selected activity'
        result.pop('timestamp_precision', None)
        result.pop('activity_date_only', None)
    return result, context
