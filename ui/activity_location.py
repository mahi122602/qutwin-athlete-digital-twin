"""Small optional location/date controls; persistent per-athlete defaults."""
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from services.activity_weather import search_places,coordinates
from database.training_location_repository import preferences

locate=components.declare_component('qutwin_activity_location',path=str(Path(__file__).with_name('location_component')))

def location_settings(athlete_id):
    key='training_location_'+str(athlete_id)
    if key not in st.session_state:
        try:st.session_state[key]=preferences(athlete_id)
        except Exception:st.session_state[key]={}
    saved=st.session_state[key]
    st.caption('Training location: '+saved.get('label','Not set')+' · Optional')
    with st.expander('Location and outdoor weather (optional)'):
        st.caption('Used only for weather around your activity. City searches and weather locations are sent to Open-Meteo. Exact coordinates are not sent to the AI recommendation service.')
        mode=st.radio('Activity setting',['Unknown','Outdoor','Indoor'],
                      index=['Unknown','Outdoor','Indoor'].index(saved.get('environment','Unknown')),key=key+'_mode',horizontal=True)
        location=saved.copy()
        current=locate(key=key+'_browser',default=None)
        if current and coordinates(current.get('latitude'),current.get('longitude')):
            st.caption('Current device location found. Use it only if you trained here.')
            if st.button('Use this as my training location',key=key+'_confirm'):
                location=dict(latitude=current['latitude'],longitude=current['longitude'],
                    timezone=current.get('timezone','UTC'),label='My training location',source='Athlete-confirmed device location',
                    environment=mode)
                st.session_state[key]=location
                st.rerun()
        query=st.text_input('Or search for your city or suburb',key=key+'_query')
        if st.button('Search location',key=key+'_search',disabled=len(query.strip())<2):
            try:st.session_state[key+'_results']=search_places(query)
            except Exception:st.warning('Location search is unavailable. You can continue without it.')
        results=st.session_state.get(key+'_results',[])
        if results:
            chosen=st.selectbox('Matching locations',range(len(results)),format_func=lambda i:results[i]['label'],key=key+'_result')
            if st.button('Use selected location',key=key+'_choose'):
                st.session_state[key]=dict(results[chosen],environment=mode);st.rerun()
        location=dict(st.session_state[key],environment=mode)
        if location.get('label'):
            st.caption('Selected: '+location['label']+'. Change it here if you trained elsewhere.')
            if st.button('Remember for future uploads',key=key+'_save'):
                try:
                    preferences(athlete_id,location);st.session_state[key]=location
                    st.success('Training location saved.')
                except Exception:st.warning('Could not remember this location. It can still be used for this upload.')
            if st.button('Forget saved location',key=key+'_forget'):
                try:
                    preferences(athlete_id,delete=True);st.session_state[key]={};st.rerun()
                except Exception:st.warning('Could not remove the saved location. Please try again.')
        st.caption('Weather estimates are provided by Open-Meteo; location search uses GeoNames.')
    return location,mode

def missing_date(frame,key,location):
    details={}
    dates=pd.to_datetime(frame.get('timestamp',pd.Series(pd.NaT,index=frame.index)),utc=True,errors='coerce')
    if dates.isna().any():
        with st.expander('Add missing activity date (optional)'):
            if len(frame)!=1:
                st.caption('This file contains several records. Dates must come from the original export; one date will not be applied to all records.')
                return details
            zone=location.get('timezone','UTC')
            zone=st.text_input('Activity timezone',value=zone,key=key+'_zone',help='For example Australia/Brisbane or Asia/Kolkata.')
            try:tz=ZoneInfo(zone)
            except Exception:st.info('Choose a valid timezone to add an activity date.');return details
            today=datetime.now(tz).date()
            choice=st.radio('When did this activity happen?',['Unknown','Today','Yesterday','Choose date'],key=key+'_when',horizontal=True)
            if choice!='Unknown':
                day=today if choice=='Today' else today-timedelta(days=1) if choice=='Yesterday' else st.date_input('Activity date',max_value=today,key=key+'_day')
                details=dict(date=day.isoformat(),timezone=zone)
                if st.checkbox('I know the start time',key=key+'_known_time'):
                    time=st.time_input('Start time',key=key+'_time')
                    try:details['timestamp']=pd.Timestamp(datetime.combine(day,time)).tz_localize(zone,ambiguous='raise',nonexistent='raise').isoformat()
                    except Exception:st.warning('That local time is ambiguous or does not exist. Choose the correct activity time.');details={}
                else:st.caption('Weather will be a daily estimate; an exact activity time will not be invented.')
    return details
