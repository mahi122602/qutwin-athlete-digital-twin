"""Isolated UI verification fixture. Never imported by the production app."""
from contextlib import ExitStack
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st
st.set_page_config(layout='wide',page_title='Coach studio — test preview')
from views.coach import studio as s
from database import coach_identity as identity
from database import connection_request_repository as cr
from ui import coach_dashboard as home
from ui import activity_explorer as explorer
from services.activity_explorer import build_explorer_data
now=datetime.now(timezone.utc)
st.session_state.setdefault('logged_in',True)
st.session_state.setdefault('role','Coach')
st.session_state.setdefault('user_id','preview-coach')
st.session_state.setdefault('coach_team',1)
names=['Divya Patel','Tina Parker','Alex Chen','Sam Taylor']
roster=[]
for i,name in enumerate(names):
    snap=dict(timestamp=(now-timedelta(days=1)).isoformat(),fatigue_score=[78,56,24,None][i],readiness_score=[22,44,76,None][i],injury_risk=['High','Medium','Low',None][i],heart_rate=143,duration_minutes=39.4,training_load=56.3)
    roster.append(dict(athlete_id=f'athlete{i}',name=name,snapshot=snap,teams='Sprint team',filename='Morning run.csv',ai_status='ready'))
upload=dict(id=10,athlete_id='athlete0',filename='Morning run.csv',uploaded_at=now,snapshot=roster[0]['snapshot'],events=['100 m','200 m'],ai_status='ready',ai_text='Review the recorded training demands with your coach before changing your training plan.',ai_model='Configured model')
review=dict(id=1,upload_id=10,coach_id='preview-coach',status='Pending',comment='',final_text='',reviewed_at=None,**{k:v for k,v in upload.items() if k!='id'})
history=pd.DataFrame([dict(timestamp=now-timedelta(days=15-i),fatigue_score=40+i%6*4,readiness_score=60-i%6*4,heart_rate=140+i,training_load=50+i,health_index=60,twin_score=60) for i in range(15)])
with ExitStack() as stack:
    mocks=[(s.db,'profile',dict(name='Jordan Ellis',coach_id='preview-coach')),(s.db,'roster',roster),(s.db,'teams',[dict(id=1,name='Sprint team',description='Sprint squad')]),(s.db,'members',[dict(athlete_id=r['athlete_id']) for r in roster]),(s,'coach_queue',[review]),(s,'list_uploads',[upload]),(s,'get_reviews',[]),(s,'get_athlete_twin_history',history),(s,'require_coach_connection',None),(identity,'my_details',{}),(cr,'get_incoming_connection_requests',[]),(cr,'get_sent_connection_requests',[]),(cr,'get_notifications',[dict(notification_id=1,notification_type='AI draft ready',created_at=now,is_read=False,message='Recommendation ready for athlete athlete0, upload #10')])]
    for module,name,value in mocks:stack.enter_context(patch.object(module,name,return_value=value))
    stack.enter_context(patch.object(home,'coach_queue',return_value=[review]))
    stack.enter_context(patch.object(home,'get_unread_notification_count',return_value=1))
    stack.enter_context(patch.object(home,'require_coach_connection',return_value=None))
    stack.enter_context(patch.object(explorer,'load_explorer_data',return_value=build_explorer_data([],legacy=history)))
    for name in ['create_team','change_member','disconnect','save_profile','delete_profile']:stack.enter_context(patch.object(s.db,name,return_value=None))
    stack.enter_context(patch.object(s,'review_recommendation',return_value=None))
    s.render()
