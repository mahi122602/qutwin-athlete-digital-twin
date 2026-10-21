"""Simple upload flow: upcoming events, files, review."""
import hashlib
import logging
import pandas as pd
import streamlit as st
from ingestion.workflow_loader import load_uploaded_file
from ingestion.adaptive_table import FIELDS
from prediction.upload_processing import process_upload
from ui.activity_location import location_settings,missing_date

EVENTS=["100 m","200 m","400 m","800 m","1500 m","5 km","10 km","Half Marathon","Marathon"]

def upload_garmin_data():
    from ui.studio_shell import chapter
    chapter('01 / ADD A CHAPTER','Choose upcoming events, add your files, then review and save. A training activity does not have to match a competition event.')
    athlete_id=str(st.session_state.user_id)
    prefix='simple_upload_'+athlete_id+'_'
    cache=st.session_state.setdefault(prefix+'files',{})
    outcomes=st.session_state.setdefault(prefix+'outcomes',{})
    st.title('Upload Activity Data')
    st.caption('Choose your upcoming events, add training files, and see your results.')
    with st.container(border=True):
        st.subheader('1. Choose your events')
        selected=st.multiselect('Which events are you preparing for?',EVENTS,key=prefix+'events')
        st.caption('These are your upcoming events. Your files can contain other training activities, including cycling.')
    with st.container(border=True):
        st.subheader('2. Upload your data')
        files=st.file_uploader('Add activity files',type=['csv','xlsx','xls','fit','gpx','tcx','xml','json','zip','tsv','txt','jsonl'],
                              accept_multiple_files=True,key=prefix+'uploader')
        st.caption('Add exports from your watch or fitness app.')
        entries=[];seen=set()
        for uploaded in files or []:
            digest=hashlib.sha256(uploaded.getvalue()).hexdigest()
            if digest in seen:continue
            seen.add(digest)
            if digest not in cache:
                entry=dict(name=uploaded.name,digest=digest,assignments=[],planned_events_only=True)
                try:
                    with st.spinner('Reading '+uploaded.name+'…'):
                        df,raw,detection=load_uploaded_file(uploaded)
                    measurements=[k for k in FIELDS if k not in ('timestamp','activity_type','latitude','longitude')]
                    if df.empty or not df.reindex(columns=measurements).notna().any().any():
                        raise ValueError('No activity measurements')
                    entry.update(df=df,raw=raw,detection=detection)
                except Exception:
                    logging.getLogger(__name__).exception('Activity import failed')
                    entry['error']='We could not read usable activity measurements. Export the original activity file again from your fitness app. Renaming a file does not change its format.'
                cache[digest]=entry
            entries.append(cache[digest])
        for digest in list(cache):
            if digest not in seen:cache.pop(digest)
    with st.container(border=True):
        st.subheader('3. Review and upload')
        location,environment=location_settings(athlete_id)
        if selected:st.write('Upcoming events: '+', '.join(selected))
        if not entries:st.caption('Add a file above to continue.')
        for entry in entries:
            st.write('**'+entry['name'].replace('*','')+'**')
            if entry.get('error'):
                st.error(entry['error']);continue
            saved=outcomes.get(entry['digest'],{}).get('status') in ('saved','already_saved')
            st.caption('Already saved' if saved else 'Ready to upload')
            if any(r.get('issues') for r in entry.get('raw',{}).get('reports',{}).values()):
                st.caption('Some optional measurements could not be read. Your usable activity data can still be saved.')
            entry['activity_details']=missing_date(entry['df'],prefix+entry['digest'],location)
            entry['location']=location
            entry['environment']=environment
            with st.expander('View activity summary'):
                names={'timestamp':'Activity time','activity_type':'Activity','duration_minutes':'Minutes',
                       'distance':'Distance (km)','heart_rate':'Average heart rate','steps':'Steps','calories':'Calories'}
                columns=[k for k in names if k in entry['df']]
                st.dataframe(entry['df'][columns].rename(columns=names).head(10),hide_index=True,use_container_width=True)
            from views.athlete.import_review import review_import
            review_import(entry,prefix+entry['digest']+'_review_',saved=saved)
            if outcomes.get(entry['digest'],{}).get('status')=='error':
                st.error('This file could not be saved. Please try again. Your earlier uploads are safe.')
        pending=[e for e in entries if outcomes.get(e['digest'],{}).get('status') not in ('saved','already_saved')]
        ready=bool(selected and pending and all(not e.get('error') for e in pending))
        if entries and not selected:st.info('Choose at least one upcoming event.')
        st.caption('Missing optional details will not stop your upload. Advice uses the information available.')
        if st.button('Upload and proceed',type='primary',disabled=not ready,key=prefix+'save'):
            with st.spinner('Saving and analysing your activities…'):
                for entry in pending:
                    try:outcomes[entry['digest']]=process_upload(athlete_id,entry,selected)
                    except Exception:
                        logging.getLogger(__name__).exception('Activity save failed')
                        outcomes[entry['digest']]={'status':'error'}
            if all(outcomes.get(e['digest'],{}).get('status') in ('saved','already_saved') for e in entries):
                st.session_state.workflow_generate_ids=[outcomes[e['digest']]['id'] for e in entries]
                st.session_state.current_page='Predictions & Coach Recommendations'
            st.rerun()
        if entries and not pending:
            st.success('Your files are saved. Identical files are not added twice.')
            st.caption('Previously saved files keep their original event plan and results.')
            if st.button('View predictions',key=prefix+'view'):
                st.session_state.current_page='Predictions & Coach Recommendations';st.rerun()
