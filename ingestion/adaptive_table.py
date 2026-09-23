"""Strict tabular import with explicit mapping and unit overrides.
Never skip malformed rows or supply missing physiological measurements.
"""
import csv
import io
import json
import re
import zipfile
from html.parser import HTMLParser
import pandas as pd

LIMIT=100*1024*1024
FIELDS={
 'timestamp':['date','activity date','start time','startdate','start date','start_date_local','day_time','date / time','begin timestamp','start timestamp'],
 'heart_rate':['avg hr','average heart rate','avg heart rate','mean heart rate','mean_heart_rate','average_heartrate','avg_heart_rate','hr'],
 'duration_minutes':['time','moving time','elapsed time','duration','total timer time','exercise duration'],
 'distance':['getdistance','get distance','total distance'],
 'sleep_hours':['sleep hours','sleep duration'],
 'training_load':['training load'], 'recovery_time':['recovery time'],
 'hydration_level':['hydration level'], 'temperature':['avg temperature','average temperature'],
 'humidity':['relative humidity'], 'previous_injury':['previous injury'],
 'calories':['energy','active calories'], 'steps':['step count'],
 'avg_speed':['average speed'], 'total_ascent':['elevation gain','total elevation gain'],
 'resting_heart_rate':['resting heart rate','resting hr'], 'hrv_ms':['hrv','rmssd','heart rate variability'],
 'session_rpe':['rpe','perceived exertion'], 'activity_type':['sport','sport type','activity type','workout type']}
UNITS={'duration_minutes':['minutes','seconds','milliseconds','hours'],
 'sleep_hours':['hours','minutes','seconds'], 'recovery_time':['hours','minutes','seconds'],
 'distance':['km','m','mi'], 'temperature':['C','F'], 'hrv_ms':['milliseconds','seconds'],
 'avg_speed':['km/h','m/s','mph'],'total_ascent':['m','ft']}
BOUNDS={'heart_rate':(20,250),'sleep_hours':(0,24),'training_load':(0,10000),
 'recovery_time':(0,720),'temperature':(-60,65),'humidity':(0,100),'previous_injury':(0,1),
 'resting_heart_rate':(20,150),'hrv_ms':(1,500),'session_rpe':(0,10),'avg_speed':(0,150),'total_ascent':(0,20000),
 'duration_minutes':(0,10080),'distance':(0,10000),'steps':(0,1000000),'calories':(0,100000)}

def key(s):
 s=re.sub(r'([a-z])([A-Z])',r'\1 \2',str(s))
 return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()

def unique(values):
 seen=set();out=[]
 for i,v in enumerate(values):
  stem=str(v).strip().lstrip('\ufeff') or f'column_{i+1}';v=stem;n=2
  while v in seen:v=f'{stem} [{n}]';n+=1
  seen.add(v);out.append(v)
 return out

def decode(data):
 if data.startswith((b'\xff\xfe',b'\xfe\xff')):return data.decode('utf-16')
 if b'\x00' in data[:1000]:return data.decode('utf-16-le')
 try:return data.decode('utf-8-sig')
 except UnicodeDecodeError:return data.decode('cp1252')

class TableParser(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
 def handle_starttag(self,tag,attrs):
  if tag=='tr':self.row=[]
  if tag in ('td','th'):
   if any(k in ('colspan','rowspan') and v!='1' for k,v in attrs):raise ValueError('Merged HTML cells need a flat CSV export.')
   self.cell=''
 def handle_data(self,s):
  if self.cell is not None:self.cell+=s
 def handle_endtag(self,tag):
  if tag in ('td','th') and self.row is not None and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
  if tag=='tr' and self.row:self.rows.append(self.row);self.row=None

def read_table(data, options=None):
 o=options or {};notes=[];meta={}
 if len(data)>LIMIT:raise ValueError('File exceeds 100 MB.')
 excel=False
 if data.startswith(b'PK'):
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   excel=any(n.startswith('xl/') for n in z.namelist())
   if sum(i.file_size for i in z.infolist())>LIMIT:raise ValueError('Expanded workbook exceeds 100 MB.')
 if excel or data.startswith(b'\xd0\xcf\x11\xe0'):
  engine='openpyxl' if excel else 'xlrd'
  try:
   book=pd.ExcelFile(io.BytesIO(data),engine=engine);meta['sheets']=book.sheet_names
   sheet=o.get('sheet') or book.sheet_names[0]
   frame=pd.read_excel(book,sheet_name=sheet,header=o.get('header_row',0),dtype=object)
  except ImportError as e:raise ValueError(f'Excel import requires {engine}; install requirements.txt.') from e
  notes.append(f'Excel workbook; selected sheet: {sheet}.')
 else:
  text=decode(data);s=text.lstrip()
  if s.startswith(('[','{')):
   try:payload=json.loads(text)
   except json.JSONDecodeError:
    try:payload=[json.loads(x) for x in text.splitlines() if x.strip()]
    except json.JSONDecodeError as e:raise ValueError(f'Invalid JSON: {e}') from e
   if isinstance(payload,dict):
    arrays=[k for k,v in payload.items() if isinstance(v,list)]
    chosen=o.get('json_key') or (arrays[0] if len(arrays)==1 else None)
    if len(arrays)>1 and not chosen:raise ValueError('JSON contains several lists; enter the record-list key in import settings.')
    payload=payload[chosen] if chosen else [payload]
   if not isinstance(payload,list) or not all(isinstance(v,dict) for v in payload):raise ValueError('JSON records must be objects with named measurements.')
   frame=pd.json_normalize(payload)
  elif re.search(r'<(?:html|table)\b',s,re.I):
   parser=TableParser();parser.feed(text);rows=parser.rows
   h=o.get('header_row',0)
   if len(rows)<=h:raise ValueError('HTML contains no table header.')
   if any(len(r)!=len(rows[h]) for r in rows[h+1:]):raise ValueError('HTML tables are not rectangular; export a single flat table.')
   frame=pd.DataFrame(rows[h+1:],columns=unique(rows[h]));notes.append('Read HTML table, regardless of filename extension.')
  elif 'urn:schemas-microsoft-com:office:spreadsheet' in s[:3000]:
   from defusedxml import ElementTree as ET
   root=ET.fromstring(data);ns='{urn:schemas-microsoft-com:office:spreadsheet}'
   sheets=root.findall(ns+'Worksheet');names=[v.get(ns+'Name',str(i)) for i,v in enumerate(sheets)];meta['sheets']=names
   chosen=o.get('sheet') or names[0];rows=[]
   for row in sheets[names.index(chosen)].iter(ns+'Row'):
    vals=[]
    for cell in row.findall(ns+'Cell'):
     index=int(cell.get(ns+'Index',len(vals)+1))
     if index>1000:raise ValueError('Spreadsheet has too many columns.')
     vals.extend(['']*max(0,index-len(vals)-1));v=cell.find(ns+'Data');vals.append(v.text if v is not None else '')
    rows.append(vals)
   width=max(map(len,rows));rows=[r+['']*(width-len(r)) for r in rows];h=o.get('header_row',0)
   frame=pd.DataFrame(rows[h+1:],columns=unique(rows[h]))
  else:
   candidates=[]
   for delimiter in ([o['delimiter']] if o.get('delimiter') else [',',';','\t','|']):
    try:rows=list(csv.reader(io.StringIO(text),delimiter=delimiter,strict=True))
    except csv.Error:continue
    for h,row in enumerate(rows[:30]):
     if 'header_row' in o and h!=o['header_row']:continue
     if len(row)<2 or any('com.samsung.' in c for c in row):continue
     width=len(row);following=[r for r in rows[h+1:h+21] if any(c.strip() for c in r)]
     match=sum(len(r)==width or (len(r)==width+1 and not r[-1].strip()) for r in following)
     letters=sum(bool(re.search('[A-Za-z]',c)) for c in row)
     if letters<2:continue
     candidates.append((match+letters/max(width,1)-h*.01,h,delimiter,rows))
   if not candidates:raise ValueError('Cannot identify a table header/delimiter. Set them in import settings or export a flat CSV.')
   _,h,delimiter,rows=max(candidates,key=lambda v:v[0]);header=rows[h];width=len(header);clean=[]
   for i,row in enumerate(rows[h+1:],h+2):
    if not any(c.strip() for c in row):continue
    while len(row)>width and not row[-1].strip():row.pop()
    if len(row)!=width:raise ValueError(f'CSV record {i}: expected {width} columns, found {len(row)}. Check quoting/delimiter; no rows were skipped.')
    clean.append(row)
   frame=pd.DataFrame(clean,columns=unique(header));meta.update(delimiter=delimiter,header_row=h)
   notes.append(f'Delimited table: header record {h+1}; separator {repr(delimiter)}.')
 if frame.empty:raise ValueError('No data records found.')
 if len(frame)>100000:raise ValueError('Use at most 100,000 records per table.')
 frame.columns=unique(frame.columns)
 return frame,dict(meta,notes=notes)

def number(value,decimal='Auto'):
 if pd.isna(value) or str(value).strip().lower() in ('','--','none','nan','n/a','null'):return None
 s=str(value).strip().replace('\u2212','-').replace('\u00a0','')
 s=re.sub(r'\s*(bpm|km|mi|m|%|°?[CF]|℃|℉|hours?|hrs?|minutes?|mins?|seconds?|secs?|ms)\s*$','',s,flags=re.I).strip()
 if decimal=='Comma':s=s.replace('.','').replace(',','.')
 elif decimal=='Dot':s=s.replace(',','')
 elif ',' in s:
  if '.' in s: return None
  if re.fullmatch(r'[-+]?\d{1,3},\d{3}',s):return None
  s=s.replace(',','.')
 try:
  n=float(s);return n if pd.notna(n) and abs(n)!=float('inf') else None
 except (ValueError,TypeError):return None

def infer_unit(field,column):
 k=key(column)
 for unit,aliases in [('milliseconds',['milliseconds','ms']),('seconds',['seconds','secs','s']),('minutes',['minutes','mins','min']),('hours',['hours','hrs','h']),('km',['km','kilometers']),('mi',['mi','miles']),('m',['m','meters']),('C',['c','celsius']),('F',['f','fahrenheit'])]:
  if any(k.endswith(' '+a) for a in aliases):return unit
 if column==field:return {'duration_minutes':'minutes','sleep_hours':'hours','recovery_time':'hours','temperature':'C','distance':'km','hrv_ms':'milliseconds','avg_speed':'km/h','total_ascent':'m'}.get(field)
 return None

def convert(v,field,col,o):
 unit=o.get('units',{}).get(field) or infer_unit(field,col) or infer_unit(field,'value '+str(v))
 if field in UNITS and unit is not None and unit not in UNITS[field]:return None
 if field=='timestamp':
  if pd.isna(v) or not str(v).strip():return pd.NaT
  s=str(v).strip();date_order=o.get('date_order','Auto')
  if re.fullmatch(r'\d{10}(?:\.\d+)?',s):return pd.to_datetime(float(s),unit='s',utc=True,errors='coerce')
  if re.fullmatch(r'\d{13}(?:\.\d+)?',s):return pd.to_datetime(float(s),unit='ms',utc=True,errors='coerce')
  if not re.search(r'\d{4}',s):return pd.NaT
  m=re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})',s)
  if m and date_order=='Auto' and int(m[1])<=12 and int(m[2])<=12 and m[1]!=m[2]:return pd.NaT
  try:
   t=pd.to_datetime(s,dayfirst=date_order=='Day first',errors='raise')
   if t.tzinfo is None:t=t.tz_localize(o.get('timezone','UTC'),ambiguous='raise',nonexistent='raise')
   return t.tz_convert('UTC')
  except (ValueError,TypeError,KeyError):return pd.NaT
 if field=='activity_type':return str(v).strip()[:100] if pd.notna(v) else None
 if field=='hydration_level':return str(v).strip().title() if str(v).strip().title() in ('Low','Medium','High') else None
 if field=='previous_injury' and str(v).lower().strip() in ('yes','true','no','false'):return int(str(v).lower().strip() in ('yes','true'))
 if field in ('duration_minutes','sleep_hours','recovery_time') and ':' in str(v):
  try:
   a=[float(x) for x in str(v).strip().split(':')]
   if len(a) not in (2,3) or any(x<0 for x in a) or any(x>=60 for x in a[1:]):return None
   if len(a)==2 and field!='duration_minutes' and not unit:return None
   seconds=a[0]*3600+a[1]*60+a[2] if len(a)==3 else (a[0]*3600+a[1]*60 if unit=='hours' else a[0]*60+a[1])
   return seconds/(60 if field=='duration_minutes' else 3600)
  except ValueError:return None
 n=number(v,o.get('decimal','Auto'))
 if n is None:return None
 if field in UNITS:
  if not unit:return None
  if field in ('duration_minutes','sleep_hours','recovery_time'):
   seconds=n*{'seconds':1,'milliseconds':.001,'minutes':60,'hours':3600}[unit]
   n=seconds/(60 if field=='duration_minutes' else 3600)
  elif field=='distance':n*= {'km':1,'m':.001,'mi':1.609344}[unit]
  elif field=='temperature' and unit=='F':n=(n-32)*5/9
  elif field=='hrv_ms' and unit=='seconds':n*=1000
  elif field=='avg_speed':n*= {'km/h':1,'m/s':3.6,'mph':1.609344}[unit]
  elif field=='total_ascent' and unit=='ft':n*=.3048
 return n

def normalise_table(raw, options=None):
 o=options or {};frame=raw.copy();notes=[];mapping={};issues=[];original_count=len(frame)
 for field,aliases in FIELDS.items():
  if field in o.get('mapping',{}):mapping[field]=o['mapping'][field];continue
  if field in frame and not any(str(c).startswith(field+' [') for c in frame):mapping[field]=field;continue
  matches=[]
  for c in frame:
   k=key(re.sub(r' \[\d+\]$','',str(c)));base=re.sub(r' (bpm|km|mi|m|c|f|celsius|fahrenheit|seconds|minutes|hours|ms)$','',k)
   if any(k==key(a) or base==key(a) or ('.' in str(c) and key(str(c).split('.')[-1])==key(a)) for a in aliases+[field]):matches.append(c)
  if len(matches)==1:mapping[field]=matches[0]
  elif len(matches)>1:
   if field=='duration_minutes' and 'Time' in matches:mapping[field]='Time'
   else:notes.append(f'Choose the source column for {field}; several columns match.')
 label=next((c for c in frame if key(c) in ('split','lap','laps')),None)
 if label and o.get('row_mode','Auto')!='All rows':
  summary=frame[label].astype(str).str.strip().str.lower().isin(['summary','total'])
  other=frame.loc[~summary,label].astype(str).str.strip().str.fullmatch(r'\d+')
  session_cols=[c for c in frame if key(c) in ('activity id','session id','activity date')]
  single_session=all(frame[c].dropna().nunique()<=1 for c in session_cols)
  if summary.sum()==1 and other.all() and single_session:frame=frame.loc[summary].copy();notes.append(f'Used whole-activity summary; {len(raw)-1} split rows remain in the raw preview.')
  elif o.get('row_mode')=='Summary only':raise ValueError('Cannot identify one unambiguous summary row.')
 if mapping.get('duration_minutes') and key(mapping['duration_minutes'])=='time' and mapping.get('timestamp') and not label and 'duration_minutes' not in o.get('mapping',{}):mapping.pop('duration_minutes')
 if o.get('time_column')==mapping.get('duration_minutes'):mapping.pop('duration_minutes',None)
 out=pd.DataFrame(index=frame.index)
 for c in frame:out['raw::'+str(c)]=frame[c]
 for field,col in mapping.items():
  if not col or col not in frame:continue
  values=frame[col]
  if field=='timestamp' and o.get('time_column') in frame:values=values.astype(str)+' '+frame[o['time_column']].astype(str)
  out[field]=values.map(lambda v:convert(v,field,col,o))
  if field in BOUNDS:
   lo,hi=BOUNDS[field];valid=pd.to_numeric(out[field],errors='coerce').between(lo,hi)
   if field=='previous_injury':valid &= out[field].isin([0,1])
   out.loc[~valid,field]=None
  bad=values.notna() & values.astype(str).str.strip().ne('') & out[field].isna()
  for i in frame.index[bad]:issues.append({'source_row':int(i)+1,'field':field,'value':str(frame.loc[i,col]),'problem':'Invalid, ambiguous, or unit not confirmed; left missing.'})
 if 'timestamp' not in out:out['timestamp']=pd.NaT
 if 'training_load' not in out:out['training_load']=float('nan')
 out['training_load_origin']='Uploaded load; scale not verified against training data'
 if {'heart_rate','duration_minutes'}.issubset(out):
  load=(out.heart_rate*out.duration_minutes/100).round(2);mask=out.training_load.isna() & load.notna()
  if mask.any():
   out.loc[mask,'training_load']=load[mask]
   out.loc[mask,'training_load_origin']='QUTwin estimate: average HR × minutes / 100'
  if mask.any():notes.append('Training load is the existing QUTwin estimate: heart rate × duration minutes / 100; not a vendor measurement.')
 for c in frame:
  if key(c) in ('fatigue score','injury risk','readiness score','twin score','health index','recommendation','athlete state'):
   out['uploaded_'+key(c).replace(' ','_')]=frame[c]
 out['_source_row']=out.index+1
 for field in ('record_kind','timestamp_origin'):
  if field in frame:out[field]=frame[field]
 return out.reset_index(drop=True),{'mapping':mapping,'notes':notes,'issues':issues,'source_rows':original_count,'activity_rows':len(out)}
