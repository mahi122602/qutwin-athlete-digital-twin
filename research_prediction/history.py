"""Prevent forecasting across incompatible model versions or missing activity dates."""
import pandas as pd

def comparable_history(frame):
    if frame is None or frame.empty:return pd.DataFrame()
    data=frame.copy()
    if 'model_version' in data and data.model_version.notna().any():
        candidates=data[data.model_version.notna()].copy()
        if 'uploaded_at' in candidates:
            candidates['_saved']=pd.to_datetime(candidates.uploaded_at,utc=True,errors='coerce')
            candidates=candidates.sort_values('_saved',na_position='first')
        latest=candidates.iloc[-1]
        data=data[data.model_version.eq(latest.model_version)]
        for c in ('model_tier','primary_event'):
            if c in data and pd.notna(latest.get(c)):data=data[data[c].eq(latest[c])]
    if 'timestamp' not in data:return data.iloc[:0]
    data['timestamp']=pd.to_datetime(data.timestamp,utc=True,errors='coerce',format='mixed')
    return data.dropna(subset=['timestamp']).sort_values('timestamp')
