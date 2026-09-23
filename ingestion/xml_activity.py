"""Unit-aware Apple Health, TCX and GPX parsing; no unrelated sample joins."""
import math
import pandas as pd
from defusedxml import ElementTree as ET

def tag(e):return e.tag.split('}')[-1]
def num(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None

def timestamp(v):return pd.to_datetime(v,utc=True,errors='coerce')
def first_text(node,name):return next((e.text for e in node.iter() if tag(e)==name and e.text),None)
def quantity(value,unit,scales):
    n=num(value);return n*scales[unit] if n is not None and unit in scales else None

def read_xml(data):
    root=ET.fromstring(data)
    if tag(root)=='HealthData':return apple(root)
    if tag(root).lower()=='gpx':return gpx(root)
    if tag(root)=='TrainingCenterDatabase':return tcx(root)
    raise ValueError('XML structure is not recognised. Export Apple Health XML, TCX, GPX, or a flat CSV with named measurements.')

def apple(root):
    records=[e.attrib for e in root if tag(e)=='Record'];rows=[];used=set()
    hrtypes={'HKQuantityTypeIdentifierHeartRate'}
    for e in root:
        if tag(e)!='Workout':continue
        a=e.attrib;start=timestamp(a.get('startDate'));end=timestamp(a.get('endDate'))
        row={'timestamp':start,'record_kind':'activity','activity_type':a.get('workoutActivityType'),
             'duration_minutes':quantity(a.get('duration'),a.get('durationUnit'),{'min':1,'s':1/60,'hr':60}),
             'distance':quantity(a.get('totalDistance'),a.get('totalDistanceUnit'),{'km':1,'m':.001,'mi':1.609344}),
             'calories':quantity(a.get('totalEnergyBurned'),a.get('totalEnergyBurnedUnit'),{'kcal':1,'kJ':1/4.184})}
        # Newer Apple exports may hold workout totals in WorkoutStatistics.
        for st in e:
            if tag(st)!='WorkoutStatistics':continue
            t=st.get('type','');unit=st.get('unit')
            if 'Distance' in t and row['distance'] is None:row['distance']=quantity(st.get('sum'),unit,{'km':1,'m':.001,'mi':1.609344})
            if t.endswith('ActiveEnergyBurned') and row['calories'] is None:row['calories']=quantity(st.get('sum'),unit,{'kcal':1,'kJ':1/4.184})
            if t.endswith('HeartRate') and unit in ('count/min','bpm'):row['heart_rate']=num(st.get('average'))
        hearts=[]
        if pd.notna(start) and pd.notna(end):
            for i,r in enumerate(records):
                t=timestamp(r.get('startDate'))
                if r.get('type') in hrtypes and r.get('unit') in ('count/min','bpm') and pd.notna(t) and start<=t<=end:
                    v=num(r.get('value'))
                    if v is not None:hearts.append(v);used.add(i)
        if row.get('heart_rate') is None and hearts:row['heart_rate']=sum(hearts)/len(hearts)
        rows.append(row)
    supported={'HKQuantityTypeIdentifierRestingHeartRate':('resting_heart_rate',{'count/min':1,'bpm':1}),
      'HKQuantityTypeIdentifierHeartRateVariabilitySDNN':('hrv_ms',{'ms':1,'s':1000}),
      'HKQuantityTypeIdentifierStepCount':('steps',{'count':1}),
      'HKQuantityTypeIdentifierActiveEnergyBurned':('calories',{'kcal':1,'kJ':1/4.184}),
      'HKQuantityTypeIdentifierHeartRate':('heart_rate',{'count/min':1,'bpm':1})}
    for i,r in enumerate(records):
        if i in used or r.get('type') not in supported:continue
        field,units=supported[r['type']];v=quantity(r.get('value'),r.get('unit'),units)
        if v is not None:rows.append({'timestamp':r.get('startDate'),field:v,'record_kind':'measurement'})
    if not rows:raise ValueError('Apple export contains no supported workout or measurement records. Include workout, heart-rate or daily-activity data.')
    return pd.DataFrame(rows)

def tcx(root):
    rows=[]
    for activity in (e for e in root.iter() if tag(e)=='Activity'):
        laps=[e for e in activity.iter() if tag(e)=='Lap'];points=[e for e in activity.iter() if tag(e)=='Trackpoint']
        dates=[timestamp(first_text(e,'Time')) for e in points];dates=[t for t in dates if pd.notna(t)]
        hr=[num(first_text(e,'Value')) for p in points for e in p if tag(e)=='HeartRateBpm'];hr=[v for v in hr if v is not None]
        duration=[num(first_text(e,'TotalTimeSeconds')) for e in laps];distance=[num(first_text(e,'DistanceMeters')) for e in laps]
        calories=[num(first_text(e,'Calories')) for e in laps]
        row={'timestamp':min(dates) if dates else first_text(activity,'Id'),'record_kind':'activity','activity_type':activity.get('Sport'),
             'duration_minutes':sum(v for v in duration if v is not None)/60 if any(v is not None for v in duration) else None,
             'distance':sum(v for v in distance if v is not None)/1000 if any(v is not None for v in distance) else None,
             'calories':sum(v for v in calories if v is not None) if any(v is not None for v in calories) else None,
             'heart_rate':sum(hr)/len(hr) if hr else None}
        if row['heart_rate'] is None:
            averages=[(num(first_text(e,'TotalTimeSeconds')),num(first_text(h,'Value'))) for e in laps for h in e if tag(h)=='AverageHeartRateBpm']
            averages=[(w,v) for w,v in averages if w and v is not None]
            if averages:row['heart_rate']=sum(w*v for w,v in averages)/sum(w for w,v in averages)
        if row['duration_minutes'] is None and len(dates)>1:row['duration_minutes']=(max(dates)-min(dates)).total_seconds()/60
        rows.append(row)
    if not rows:raise ValueError('TCX contains no Activity records.')
    return pd.DataFrame(rows)

def gpx(root):
    rows=[]
    for track in (e for e in root if tag(e)=='trk'):
        dates=[];hearts=[];distance=0.;valid_segments=0
        for segment in (e for e in track if tag(e)=='trkseg'):
            prev=None
            for p in segment:
                if tag(p)!='trkpt':continue
                t=timestamp(first_text(p,'time'))
                if pd.notna(t):dates.append(t)
                h=num(first_text(p,'hr'))
                if h is not None:hearts.append(h)
                lat,lon=num(p.get('lat')),num(p.get('lon'))
                if lat is None or lon is None or not -90<=lat<=90 or not -180<=lon<=180:prev=None;continue
                current=(math.radians(lat),math.radians(lon))
                if prev:
                    a=math.sin((current[0]-prev[0])/2)**2+math.cos(prev[0])*math.cos(current[0])*math.sin((current[1]-prev[1])/2)**2
                    distance+=6371.0088*2*math.asin(math.sqrt(min(1,max(0,a))));valid_segments+=1
                prev=current
        rows.append({'timestamp':min(dates) if dates else None,'record_kind':'activity','activity_type':first_text(track,'type'),
          'duration_minutes':(max(dates)-min(dates)).total_seconds()/60 if len(dates)>1 else None,
          'distance':distance if valid_segments else None,'heart_rate':sum(hearts)/len(hearts) if hearts else None})
    if not rows:raise ValueError('GPX has no recorded tracks. A planned route alone cannot provide activity duration or heart rate.')
    return pd.DataFrame(rows)
