"""Measured-data importer; no fabricated physiological defaults.
ZIPs are processed in memory, never extracted. One uploaded archive remains one file.
"""
import io
import json
import zipfile
from pathlib import Path
import pandas as pd

MAX_BYTES=100*1024*1024
SUPPORTED={'.csv','.xlsx','.xls','.json','.xml','.fit','.gpx','.tcx'}
ALIASES={
 'timestamp':['timestamp','date','activity_date','activity date','start_time','startdate','day_time','date / time'],
 'heart_rate':['heart_rate','avg hr','average heart rate','mean_heart_rate','avg_heart_rate','average_heart_rate'],
 'sleep_hours':['sleep_hours','sleep hours'], 'training_load':['training_load','training load'],
 'recovery_time':['recovery_time','recovery time'], 'hydration_level':['hydration_level','hydration level'],
 'temperature':['temperature'], 'humidity':['humidity'], 'previous_injury':['previous_injury'],
 'duration_minutes':['duration_minutes'], 'distance':['distance'], 'calories':['calories'],
 'steps':['steps','step_count','count'], 'avg_speed':['avg_speed'], 'total_ascent':['total_ascent']}


def normalise(frame):
    from ingestion.adaptive_table import normalise_table
    return normalise_table(frame)[0]


def xml_records(data):
    try:
        from defusedxml import ElementTree
    except ModuleNotFoundError as exc:
        raise ValueError('XML import needs defusedxml. Run python -m pip install -r requirements.txt and restart.') from exc
    from ingestion.xml_activity import read_xml
    return read_xml(data)


def read_raw(name,data,options=None):
    from ingestion.adaptive_table import read_table
    ext=Path(name).suffix.lower()
    if ext=='.fit' or data[8:12]==b'.FIT':
        from fitparse import FitFile
        sessions=[m.get_values() for m in FitFile(io.BytesIO(data)).get_messages('session')]
        frame=pd.DataFrame([{'timestamp':s.get('start_time'),'heart_rate':s.get('avg_heart_rate'),
            'duration_minutes':s.get('total_timer_time')/60 if s.get('total_timer_time') is not None else None,
            'distance':s.get('total_distance')/1000 if s.get('total_distance') is not None else None,
            'activity_type':str(s.get('sport') or ''),'record_kind':'activity'} for s in sessions])
        if frame.empty:raise ValueError('No activity sessions in FIT file.')
        return frame,{'notes':['FIT session records.']}
    if data.lstrip().startswith(b'<') and b'urn:schemas-microsoft-com:office:spreadsheet' not in data[:3000] and not any(v in data[:1000].lower() for v in (b'<table',b'<html')):
        return xml_records(data),{'notes':['Supported XML activity records; unrelated samples are not automatically joined.']}
    return read_table(data,options)


def parse_file(name,data,options=None):
    from ingestion.adaptive_table import normalise_table
    raw,_=read_raw(name,data,options)
    return normalise_table(raw,options)[0]


def load_uploaded_file(uploaded,options=None):
    from ingestion.adaptive_table import normalise_table
    data=uploaded.getvalue();options=options or {}
    if len(data)>MAX_BYTES:raise ValueError('Maximum upload size is 100 MB.')
    name=uploaded.name;members=[(name,data)];tables={};reports={};frames=[]
    if data.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if not any(n.startswith('xl/') for n in archive.namelist()):
                files=[f for f in archive.infolist() if not f.is_dir() and Path(f.filename).suffix.lower() in SUPPORTED|{'.tsv','.txt','.jsonl'}]
                if len(files)>300 or sum(f.file_size for f in archive.infolist())>MAX_BYTES:raise ValueError('Use at most 300 files and 100 MB uncompressed.')
                if len({f.filename for f in files})!=len(files):raise ValueError('Archive contains duplicate filenames. Export files with unique names so their mappings remain unambiguous.')
                members=[(f.filename,archive.read(f)) for f in files]
    if not members:raise ValueError('No supported files inside archive.')
    for member,payload in members:
        opt=options.get('members',{}).get(member,options)
        try:
            raw,meta=read_raw(member,payload,opt)
            if len(raw)>100000:raise ValueError('Use at most 100,000 records per table or activity export.')
            frame,report=normalise_table(raw,opt)
            if 'record_kind' not in frame:frame['record_kind']='activity'
            if opt.get('activity_timestamp') and len(frame)==1:
                from ingestion.adaptive_table import convert
                t=convert(opt['activity_timestamp'],'timestamp','timestamp',opt)
                if pd.isna(t):raise ValueError('The entered activity date/time is ambiguous or invalid. Include an offset, for example 2026-06-25T06:15:37+10:00.')
                frame['timestamp']=t;frame['timestamp_origin']='Confirmed by athlete'
            # Preserve a filename date as a suggestion only: it may be export time.
            import re
            match=re.search(r'(20\d{12})(?=\D|$)',Path(member).stem)
            if match and frame.timestamp.isna().all():
                t=pd.to_datetime(match[1],format='%Y%m%d%H%M%S',errors='coerce')
                if pd.notna(t):report['date_candidate']=str(t)
            if not frame.reindex(columns=[k for k in __import__('ingestion.adaptive_table',fromlist=['FIELDS']).FIELDS if k not in ('timestamp','activity_type')]).notna().any().any():
                report.setdefault('notes',[]).append('No usable athlete measurements mapped. Review columns and units; this table cannot be processed until measurements are recognised.')
        except (ValueError,KeyError,UnicodeError) as exc:raise ValueError(f'{member}: {exc}') from exc
        tables[member]=raw;reports[member]=dict(meta,**report)
        if len(members)>1:frame['archive_member']=member
        frames.append(frame)
    return pd.concat(frames,ignore_index=True), {'tables':tables,'reports':reports}, {'source':'Activity export','file_type':Path(name).suffix.lstrip('.')}
