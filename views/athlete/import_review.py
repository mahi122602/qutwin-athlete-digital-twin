"""Per-file import settings; repairs reparse original bytes, not prior output."""
import io
from zoneinfo import ZoneInfo
import streamlit as st
from ingestion.adaptive_table import FIELDS,UNITS
from ingestion.workflow_loader import load_uploaded_file

def review_import(entry,prefix,saved=False):
 raw=entry.get('raw',{});tables=raw.get('tables',{});reports=raw.get('reports',{})
 for report in reports.values():
  for note in report.get('notes',[]):st.caption(note)
  if report.get('issues'):st.warning(f"{len(report['issues'])} values need review. Unknown values remain blank.")
 with st.expander('Review columns, units and file format',expanded=bool(entry.get('error'))):
  names=list(tables) or [entry['name']]
  member=st.selectbox('Table / archive member',names,key=prefix+'member')
  frame=tables.get(member);columns=list(frame.columns) if frame is not None else []
  report=reports.get(member,{})
  current=entry.get('options',{}).get('members',{}).get(member,{})
  if columns and st.button('Suggest column mappings using AI',key=prefix+'ai_mapping',disabled=saved):
   from ingestion.ai_mapping import suggest_columns
   try:
    with st.spinner('Reviewing column names…'):entry['mapping_suggestion']=suggest_columns(columns)
   except ValueError as exc:st.warning(str(exc))
  suggestion=entry.get('mapping_suggestion')
  if suggestion:
   st.caption('AI suggestion uses column names only. Confirm columns and units before applying; no measurements have changed.')
   st.json(suggestion)
  candidate=report.get('date_candidate')
  if candidate:st.info('The filename contains '+candidate+'. It could be the activity or export date. Confirm the actual activity time below; it is not automatically used.')
  def select(label,choices,value,key):return st.selectbox(label,choices,index=choices.index(value) if value in choices else 0,key=prefix+key)
  with st.form(prefix+'form'):
   st.caption('Confirm source columns and units. Canonical temperature is °C, distance km, sleep/recovery hours. Do not guess unknown measurements.')
   c1,c2,c3=st.columns(3)
   with c1:
    delimiter=select('Separator',['Auto',',',';','Tab','|'],current.get('delimiter','Auto'),'delimiter')
    header=st.number_input('Header row (0 = automatic)',min_value=0,max_value=30,value=current.get('header_row',-1)+1,key=prefix+'header')
    decimal=select('Decimal convention',['Auto','Dot','Comma'],current.get('decimal','Auto'),'decimal')
   with c2:
    order=select('Date order',['Auto','Day first','Month first'],current.get('date_order','Auto'),'order')
    timezone=st.text_input('Timezone for dates without an offset',value=current.get('timezone','UTC'),key=prefix+'timezone')
    mode=select('Activity rows',['Auto','All rows','Summary only'],current.get('row_mode','Auto'),'mode')
   with c3:
    sheets=report.get('sheets',[])
    sheet=select('Worksheet',sheets,current.get('sheet'),'sheet') if sheets else None
    json_key=st.text_input('JSON record-list key (if needed)',value=current.get('json_key',''),key=prefix+'json')
    activity_timestamp=st.text_input('Known activity date/time (single-activity files only)',value=current.get('activity_timestamp',''),key=prefix+'activity_date',help='Enter the actual activity time with timezone, for example 2026-06-25T06:15:37+10:00. Leave blank if unknown.')
    time_col=select('Separate time-of-day column',['None']+columns,current.get('time_column','None'),'time')
   mapping={};units={};cols=st.columns(3)
   for i,field in enumerate(FIELDS):
    with cols[i%3]:
     chosen=select(field,['Unmapped']+columns,current.get('mapping',{}).get(field,report.get('mapping',{}).get(field,'Unmapped')),'map_'+field)
     mapping[field]=None if chosen=='Unmapped' else chosen
     if field in UNITS:
      unit=select(field+' unit',['Auto']+UNITS[field],current.get('units',{}).get(field,'Auto'),'unit_'+field)
      if unit!='Auto':units[field]=unit
   apply=st.form_submit_button('Apply import settings',disabled=saved)
  if frame is not None:st.dataframe(frame.head(100),hide_index=True,use_container_width=True)
  if report.get('issues'):st.dataframe(report['issues'][:100],hide_index=True,use_container_width=True)
  if apply:
   try:
    ZoneInfo(timezone)
    new=dict(mapping=mapping,units=units,decimal=decimal,date_order=order,timezone=timezone,row_mode=mode)
    if delimiter!='Auto':new['delimiter']='\t' if delimiter=='Tab' else delimiter
    if header:new['header_row']=int(header)-1
    if sheet:new['sheet']=sheet
    if json_key:new['json_key']=json_key
    if activity_timestamp.strip():new['activity_timestamp']=activity_timestamp.strip()
    if time_col!='None':new['time_column']=time_col
    if any(new.get(k)!=current.get(k) for k in ('sheet','header_row','delimiter','json_key')):
     new.pop('mapping');new.pop('units')
    options=entry.setdefault('options',{});options.setdefault('members',{})[member]=new
    data=io.BytesIO(entry['bytes']);data.name=entry['name']
    df,raw,detection=load_uploaded_file(data,options)
    entry.update(df=df,raw=raw,detection=detection,revision=entry.get('revision',0)+1)
    entry.pop('error',None);entry.pop('original_df',None)
    st.rerun()
   except Exception as exc:st.error(str(exc))
