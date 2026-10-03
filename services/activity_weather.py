"""Optional weather estimates, isolated from measured physiological inputs."""
import json
import math
from urllib.request import urlopen
from urllib.parse import urlencode
from functools import lru_cache
from datetime import datetime, timezone
import pandas as pd

def coordinates(lat,lon):
    try:
        lat,lon=float(lat),float(lon)
        return (lat,lon) if math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180 else None
    except (ValueError,TypeError):return None

def request_json(url, params):
    with urlopen(url+'?'+urlencode(params),timeout=8) as response:
        return json.loads(response.read(2_000_000))

@lru_cache(maxsize=128)
def search_places(query):
    if len(query.strip())<2:return []
    data=request_json('https://geocoding-api.open-meteo.com/v1/search',
                      dict(name=query.strip()[:150],count=8,language='en',format='json'))
    return [dict(latitude=r['latitude'],longitude=r['longitude'],
                 label=', '.join(str(r[k]) for k in ('name','admin1','country') if r.get(k)),
                 timezone=r.get('timezone','UTC'),source='Chosen location')
            for r in data.get('results',[]) if coordinates(r.get('latitude'),r.get('longitude'))]

@lru_cache(maxsize=256)
def hourly_weather(lat,lon,start,end,day):
    # Recent values are archived forecasts, not station observations.
    age=(datetime.now(timezone.utc).date()-pd.Timestamp(start).date()).days
    recent=age<6
    host='https://api.open-meteo.com/v1/forecast' if recent else 'https://archive-api.open-meteo.com/v1/archive'
    data=request_json(host,dict(latitude=lat,longitude=lon,start_date=start,end_date=end,
                       hourly='temperature_2m,relative_humidity_2m',timezone='GMT'))
    return data.get('hourly',{}), 'Open-Meteo recent forecast archive' if recent else 'Open-Meteo historical reanalysis'

def weather_context(record, location=None, environment='Unknown', now=None):
    if environment!='Outdoor':
        return dict(status='skipped',message='Outdoor weather was not used for an indoor or unspecified setting.')
    gps=coordinates(record.get('latitude'),record.get('longitude'))
    fallback=coordinates((location or {}).get('latitude'),(location or {}).get('longitude'))
    point=gps or fallback
    if not point:return dict(status='missing_location',message='No activity location supplied; analysis continues without weather.')
    timestamp=pd.to_datetime(record.get('timestamp'),utc=True,errors='coerce')
    # A day-only input does not become a made-up midnight activity timestamp.
    day=record.get('activity_date_only')
    if pd.isna(day):day=None
    if record.get('timestamp_precision')=='day':timestamp=pd.NaT
    if pd.isna(timestamp) and not day:
        return dict(status='missing_date',message='Activity date is unknown; analysis continues without weather.')
    now=pd.Timestamp(now or datetime.now(timezone.utc))
    start=timestamp if pd.notna(timestamp) else pd.Timestamp(day,tz=record.get('activity_timezone','UTC')).tz_convert('UTC')
    if start>now:return dict(status='future',message='The activity date is in the future; historical weather was not added.')
    duration=pd.to_numeric(record.get('duration_minutes'),errors='coerce')
    if day and pd.isna(timestamp):
        end=(pd.Timestamp(day,tz=record.get('activity_timezone','UTC'))+pd.DateOffset(days=1)).tz_convert('UTC')
        resolution='Daily average; activity time unknown'
    else:
        minutes=float(duration) if pd.notna(duration) and 0<float(duration)<=10080 else 1
        end=start+pd.Timedelta(minutes=minutes)
        resolution='Session average at hourly resolution'
    if end>now:return dict(status='incomplete',message='This activity has not finished yet; historical weather was not added.')
    try:
        hourly,source=hourly_weather(round(point[0],3),round(point[1],3),
            start.date().isoformat(),end.date().isoformat(),now.date().isoformat())
        times=pd.to_datetime(hourly.get('time',[]),utc=True)
        # Hourly samples represent overlapping one-hour bins, duration weighted.
        weights=[max(0,(min(t+pd.Timedelta(hours=1),end)-max(t,start)).total_seconds()) for t in times]
        values={}
        for field,key,bounds in [('temperature','temperature_2m',(-60,65)),('humidity','relative_humidity_2m',(0,100))]:
            seq=hourly.get(key,[])
            valid=[(float(v),w) for v,w in zip(seq,weights) if v is not None and w>0
                   and math.isfinite(float(v)) and bounds[0]<=float(v)<=bounds[1]]
            coverage=sum(w for _,w in valid)/(end-start).total_seconds()
            if valid and coverage>=.9:values[field]=round(sum(v*w for v,w in valid)/sum(w for _,w in valid),2)
        if len(values)!=2:return dict(status='unavailable',message='Weather coverage is incomplete; analysis continues without weather.')
        return dict(status='available',**values,source=source,resolution=resolution,
                    location_source='Activity GPS' if gps else (location or {}).get('source','Saved training location'),
                    location_label='Recorded activity location' if gps else (location or {}).get('label','Chosen location'),
                    estimated=True,used_in_numeric_model=False,
                    message='Estimated outdoor conditions for AI advice; not a wearable measurement.')
    except Exception:
        return dict(status='unavailable',message='Weather is temporarily unavailable; your activity can still be analysed.')

def activity_details(frame, details):
    result=frame.copy()
    # Manual dates apply only to a single-record export, never every day in an archive.
    if len(result)==1 and pd.isna(pd.to_datetime(result.iloc[0].get('timestamp'),utc=True,errors='coerce')):
        if details.get('timestamp'):
            result.loc[result.index[0],'timestamp']=pd.Timestamp(details['timestamp'])
            result.loc[result.index[0],'timestamp_origin']='Athlete confirmed'
        elif details.get('date'):
            result.loc[result.index[0],'activity_date_only']=details['date']
            result.loc[result.index[0],'activity_timezone']=details.get('timezone','UTC')
    return result
