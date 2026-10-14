"""Coach studio: live database data only, shared entry points for athlete detail."""
from pathlib import Path
from datetime import datetime,timezone
import math
import pandas as pd
import streamlit as st
from html import escape
from database import coach_studio as db
from database.access_control import require_coach_connection
from database.workflow_repository import list_uploads,coach_queue,review_recommendation,get_reviews
from database.twin_repository import get_athlete_twin_history
from ui.coach_shell import heading,go,shell,PAGES,badge,attention_card,sign_out
from ui.studio_shell import score_ribbon,style_chart



def number(x):
    try:
        x=float(x);return x if math.isfinite(x) and 0<=x<=100 else None
    except (TypeError,ValueError):return None

def attention(snapshot,now=None):
    """Review priority, not an injury probability; unknown inputs stay unknown."""
    s=snapshot or {};f=number(s.get('fatigue_score'));r=number(s.get('readiness_score'))
    injury=str(s.get('injury_risk') or '').title()
    stamp=pd.to_datetime(s.get('timestamp'),utc=True,errors='coerce')
    age=(pd.Timestamp(now or datetime.now(timezone.utc))-stamp).total_seconds() if not pd.isna(stamp) else None
    if age is None or age<0 or age>7*86400:return 'Not assessed'
    if (f is not None and f>=70) or (r is not None and r<30) or injury=='High':return 'High'
    if (f is not None and f>=45) or (r is not None and r<60) or injury=='Medium':return 'Medium'
    if f is None or r is None or injury!='Low':return 'Not assessed'
    return 'Low'


def selected(roster):
    if not roster:st.info('Connect with an athlete to view their records.');return None
    ids=[str(x['athlete_id']) for x in roster];names={str(x['athlete_id']):x['name'] for x in roster}
    current=str(st.session_state.get('coach_athlete',''));idx=ids.index(current) if current in ids else 0
    aid=st.selectbox('Connected athlete',ids,index=idx,format_func=lambda x:f'{names[x]} · {x}',key='cs_select_'+st.session_state.coach_page)
    st.session_state.coach_athlete=aid;require_coach_connection(st.session_state.user_id,aid);return aid

def table_roster(roster,key='roster'):
    if not roster:st.info('No athletes match this view.');return
    for col,title in zip(st.columns([2.3,1.3,1.2,1.4,1.2,.85]),['Athlete','Teams','Fatigue','Injury estimate','Attention','Open']):
        col.markdown('<div class="cs-table-head">'+title+'</div>',unsafe_allow_html=True)
    for x in roster:
        snap=x.get('snapshot') or {};f=number(snap.get('fatigue_score'))
        fl='Not assessed' if f is None else 'High' if f>=70 else 'Medium' if f>=45 else 'Low'
        injury=str(snap.get('injury_risk') or 'Not assessed').title()
        if injury not in ('High','Medium','Low'):injury='Not assessed'
        with st.container(key='cs_row_'+key+'_'+str(x['athlete_id'])):
            cols=st.columns([2.3,1.3,1.2,1.4,1.2,.85],vertical_alignment='center')
            cols[0].markdown('<div class="cs-name">'+escape(x['name'])+'</div><div class="cs-sub">'+escape(str(x['athlete_id']))+'</div>',unsafe_allow_html=True)
            cols[1].write(x.get('teams') or '—')
            cols[2].markdown(badge(fl),unsafe_allow_html=True)
            cols[3].markdown(badge(injury),unsafe_allow_html=True)
            cols[4].markdown(badge(attention(snap)),unsafe_allow_html=True)
            cols[5].button('View →',key='view_'+key+'_'+str(x['athlete_id']),on_click=go,args=('Athlete Detail',str(x['athlete_id'])),help='Open '+x['name'])
    st.caption('Attention uses the latest dated assessment. Unknown or stale evidence is not labelled low risk. These are research estimates.')


def dashboard(roster):
    from ui.coach_dashboard import render_dashboard
    return render_dashboard(roster, attention)


def _legacy_dashboard(roster):
    heading('A clearer view. A closer team.', 'Welcome back, '+st.session_state.coach_display_name+'. Your athletes, priorities and coaching decisions in one place.')
    queue=[x for x in coach_queue(str(st.session_state.user_id)) if x['status']=='Pending']
    for col,level,description in zip(st.columns(3),['High','Medium','Low'],['Prioritise a coach review','Monitor changes and recovery','Lower current review priority']):
        with col:attention_card(level,sum(attention(x.get('snapshot'))==level for x in roster),description)
    unknown=sum(attention(x.get('snapshot'))=='Not assessed' for x in roster)
    st.caption(f"{len(roster)} connected athletes · {unknown} not assessed · {len(queue)} drafts awaiting review")
    st.subheader('What needs your attention')
    left,right=st.columns([1.3,1])
    with left:
        priorities=[x for x in roster if attention(x.get('snapshot')) in ('High','Medium')]
        for x in priorities[:3]:
            with st.container(border=True):
                st.markdown(badge(attention(x.get('snapshot')))+' <strong>'+escape(x['name'])+'</strong>',unsafe_allow_html=True)
                st.button('Review athlete →',key='priority_'+str(x['athlete_id']),on_click=go,args=('Athlete Detail',str(x['athlete_id'])))
        if not priorities:st.info('No elevated review priorities in the available assessments. Unassessed athletes still need sufficient evidence.')
    with right:
        with st.container(border=True):
            st.subheader('Your judgement matters')
            st.write(f'{len(queue)} AI drafts await your review.')
            st.button('Review AI drafts →',type='primary',on_click=go,args=('Reviews',),use_container_width=True)
        if unknown:st.button('Check incomplete assessments →',on_click=go,args=('Intelligence',),use_container_width=True)
    st.subheader('Across your teams')
    teams=db.teams()
    if not teams:
        st.info('Create a team to organise your connected athletes.')
        st.button('Create your first team →',on_click=go,args=('Teams',))
    for team in teams[:6]:
        ids={str(r['athlete_id']) for r in db.members(team['id'])};group=[x for x in roster if str(x['athlete_id']) in ids]
        with st.container(border=True):
            a,b=st.columns([4,1]);a.markdown('**Team '+str(team['id'])+' · '+team['name']+'**')
            a.caption(' · '.join(f'{sum(attention(x.get("snapshot"))==level for x in group)} {level.lower()}' for level in ['High','Medium','Low','Not assessed']))
            b.button('Open →',key='dashteam'+str(team['id']),on_click=go,args=('Team Detail',None,team['id']))
    st.caption('Team counts summarise individual review priorities; they are not a team injury probability.')


def athletes(roster):
    heading('Your athletes','Connected athletes only. Find a name, review their status and open their record.')
    search,team_col,status_col=st.columns([2.3,1.2,1.2])
    with search:
        names={str(x['athlete_id']):x['name'] for x in roster}
        picked=st.selectbox('Find athlete',list(names),index=None,format_func=lambda x:names[x]+' · '+x,placeholder='Start typing a name…',key='coach_roster_search') if names else None
    with team_col:
        teams=db.teams();tid=st.selectbox('Team',[None]+[t['id'] for t in teams],format_func=lambda x:'All teams' if x is None else next(t['name'] for t in teams if t['id']==x))
    with status_col:level=st.selectbox('Attention',['All','High','Medium','Low','Not assessed'],key='coach_attention_filter')
    ids={str(x['athlete_id']) for x in db.members(tid)} if tid is not None else None
    shown=[x for x in roster if (not picked or str(x['athlete_id'])==picked) and (ids is None or str(x['athlete_id']) in ids) and (level=='All' or attention(x.get('snapshot'))==level)]
    table_roster(shown)


def teams_page(roster):
    heading('Your teams','Organise connected athletes. Team summaries count individual assessments.')
    with st.expander('Create team'):
        with st.form('create_team'):
            name=st.text_input('Team name',max_chars=100);desc=st.text_area('Description',max_chars=2000)
            if st.form_submit_button('Create team',type='primary'):db.create_team(name,desc);st.rerun()
    teams=db.teams();rows=[]
    for t in teams:
        ids={r['athlete_id'] for r in db.members(t['id'])};group=[x for x in roster if x['athlete_id'] in ids]
        rows.append({'Team number':t['id'],'Team':t['name'],'Members':len(group),**{k:sum(attention(x.get('snapshot'))==k for x in group) for k in ('High','Medium','Low','Not assessed')}})
    if not rows:st.info('No teams yet. Create a team above.');return
    for row in rows:
        with st.container(border=True):
            a,b=st.columns([5,1]);a.markdown('**Team '+str(row['Team number'])+' · '+row['Team']+'**')
            a.caption(str(row['Members'])+' members · '+' · '.join(str(row[k])+' '+k.lower() for k in ('High','Medium','Low','Not assessed')))
            b.button('View →',key='teamview'+str(row['Team number']),on_click=go,args=('Team Detail',None,row['Team number']))

def team_detail(roster):
    tid=st.session_state.get('coach_team');team=next((t for t in db.teams() if t['id']==tid),None)
    if not team:st.info('Choose a team from Teams.');return
    heading(f"Team {tid} · {team['name']}",team['description'])
    ids={r['athlete_id'] for r in db.members(tid)};group=[x for x in roster if x['athlete_id'] in ids]
    for col,k in zip(st.columns(4),['High','Medium','Low','Not assessed']):col.metric(k,sum(attention(x.get('snapshot'))==k for x in group))
    table_roster(group,'team_roster')
    available={str(x['athlete_id']):x['name'] for x in roster if x['athlete_id'] not in ids}
    with st.expander('Manage team members'):
        if available:
            aid=st.selectbox('Add connected athlete',list(available),format_func=lambda x:available[x])
            if st.button('Add to team'):db.change_member(tid,aid);st.rerun()
        if group:
            choices={str(x['athlete_id']):x['name'] for x in group};aid=st.selectbox('Remove member',list(choices),format_func=lambda x:choices[x])
            st.caption('Removing a team member keeps their coach connection and account.')
            if st.button('Remove from this team'):db.change_member(tid,aid,False);st.rerun()

def chart_history(aid):
    import plotly.express as px
    history=get_athlete_twin_history(aid)
    if history.empty:st.info('No activity data yet.');return
    keys=[k for k in ('fatigue_score','readiness_score','heart_rate','training_load','sleep_hours') if k in history and pd.to_numeric(history[k],errors='coerce').notna().any()]
    if not keys:st.info('No usable numeric measurements to plot.');return
    metric=st.selectbox('Measurement',keys,format_func=lambda s:s.replace('_',' ').title())
    d=history.dropna(subset=['timestamp']).sort_values('timestamp')
    st.caption(f'{len(history)-len(d)} undated records are excluded from time trends.')
    if d.empty:st.info('Activity dates are missing. Records remain available in History.');return
    fig=px.line(d,x='timestamp',y=metric,markers=True,labels={'timestamp':'Activity date',metric:metric.replace('_',' ').title()})
    st.plotly_chart(style_chart(fig),use_container_width=True)

def athlete_detail(roster):
    aid=selected(roster)
    if not aid:return
    row=next(x for x in roster if str(x['athlete_id'])==aid)
    heading(row['name'],'Connected athlete · Recorded data and research estimates')
    score_ribbon(row.get('snapshot') or {})
    mode=st.radio('View',['Overview','Trends','Forecasting','Recommendations','History'],horizontal=True,key='cs_detail_tab')
    if mode=='Trends':chart_history(aid)
    elif mode=='Forecasting':forecast(aid)
    elif mode=='Recommendations':reviews(aid)
    elif mode=='History':history_page(aid)
    else:
        s=row.get('snapshot') or {};cols=st.columns(3)
        for col,label,key in zip(cols,['Heart rate (bpm)','Duration (min)','Training load (proxy)'],['heart_rate','duration_minutes','training_load']):
            v=pd.to_numeric(s.get(key),errors='coerce');col.metric(label,f'{v:.1f}' if pd.notna(v) and math.isfinite(v) else 'Not recorded')
        st.caption('Latest file: '+str(row.get('filename') or 'No upload yet'))
        if row.get('ai_status')=='ready':st.success('An AI draft is available for coach review.')
        else:st.info('No AI draft available for the latest upload.')
        st.button('Review recommendations',on_click=go,args=('Reviews',aid))

def history_page(aid):
    uploads=list_uploads(aid);revs=get_reviews(aid)
    if not uploads:st.info('No saved uploads.');return
    rows=[]
    for u in uploads:
        s=u['snapshot'];r=next((r for r in revs if r['upload_id']==u['id']),{})
        rows.append({'Upload':u['id'],'File':u['filename'],'Saved':str(u['uploaded_at']),'Activity date':str(s.get('timestamp') or 'Unknown'),'Fatigue':number(s.get('fatigue_score')),'Injury estimate':s.get('injury_risk') or 'Not assessed','Readiness':number(s.get('readiness_score')),'AI draft':u['ai_status'],'Coach review':r.get('status','No review')})
    frame=pd.DataFrame(rows)
    st.dataframe(frame,hide_index=True,use_container_width=True)
    st.download_button('Export history CSV',frame.to_csv(index=False).encode('utf-8'),file_name='athlete_history.csv',mime='text/csv')
    choice=st.selectbox('Open saved assessment',[u['id'] for u in uploads],format_func=lambda id:next(u['filename'] for u in uploads if u['id']==id))
    u=next(u for u in uploads if u['id']==choice);score_ribbon(u['snapshot'])
    with st.expander('AI draft and coach feedback'):
        st.markdown(u.get('ai_text') or 'No draft generated.')
        for r in revs:
            if r['upload_id']==choice:st.markdown(f"**{r['status']}** · {r.get('final_text') or r.get('comment') or ''}")

def forecast(aid,evaluation=False):
    from forecasting.validated import build_forecast_bundle
    import plotly.graph_objects as pg
    history=get_athlete_twin_history(aid)
    try:b=build_forecast_bundle(history,horizon=7)
    except ValueError as e:st.info(str(e)+'. Add dated activity measurements to build a forecast.');return
    if evaluation:
        st.caption('Chronological holdout results, compared with a last-value baseline. This is not a guarantee of future accuracy.')
        if b.evaluation.empty:st.info('Not evaluated: more dated observations are needed for separate selection, calibration and test windows.')
        else:st.dataframe(b.evaluation,hide_index=True,use_container_width=True)
        st.dataframe(b.model_weights,hide_index=True,use_container_width=True);return
    st.caption(f'{b.data_points} observed days · '+str(b.table.Confidence.iloc[0]))
    if pd.Timestamp(b.table.Date.iloc[-1]).date()<datetime.now(timezone.utc).date():
        st.warning('This forecast follows the last recorded activity and ends in the past. A recent dated upload is needed for an up-to-date outlook.')
    options=[c for c in ('Fatigue forecast','Readiness forecast','Digital Twin score','Health index') if c in b.table]
    if not options:st.info('No forecastable metrics are available.');return
    metric=st.selectbox('Forecast metric',options)
    fig=pg.Figure();fig.add_trace(pg.Scatter(x=b.table.Date,y=b.table[metric],name=metric,mode='lines+markers'))
    if b.table[metric+' lower'].notna().any():
        fig.add_trace(pg.Scatter(x=b.table.Date,y=b.table[metric+' upper'],line=dict(width=0),showlegend=False))
        fig.add_trace(pg.Scatter(x=b.table.Date,y=b.table[metric+' lower'],line=dict(width=0),fill='tonexty',name='Empirical uncertainty band'))
    fig.update_yaxes(range=[0,100]);st.plotly_chart(style_chart(fig),use_container_width=True)
    st.info('Injury probability is not validated. Limited history can produce a flat baseline; the app does not invent day-to-day changes.')
    st.dataframe(b.table,hide_index=True,use_container_width=True)

def reviews(aid=None):
    queue=coach_queue(str(st.session_state.user_id))
    if aid and st.checkbox('Show only selected athlete',value=True,key='filter_review_athlete'):queue=[r for r in queue if str(r['athlete_id'])==aid]
    status=st.radio('Review status',['Pending','Completed','All'],horizontal=True)
    queue=[r for r in queue if status=='All' or (r['status']=='Pending')==(status=='Pending')]
    if not queue:st.info('No recommendations in this view.');return
    ids=[r['id'] for r in queue];target=st.session_state.get('coach_upload');initial=next((i for i,r in enumerate(queue) if r['upload_id']==target),0)
    pick=st.selectbox('Recommendation',ids,index=initial,format_func=lambda i:next(f"{r['athlete_id']} · {r['filename']} · {r['status']}" for r in queue if r['id']==i))
    r=next(r for r in queue if r['id']==pick);require_coach_connection(st.session_state.user_id,r['athlete_id'])
    st.caption(f"Source upload #{r['upload_id']} · {r['uploaded_at']} · Model: {r.get('ai_model') or 'Unknown'}")
    snap=r['snapshot'] or {}
    st.caption('AI draft · Coach approval required. Injury categories are experimental, not validated probabilities.')
    with st.expander('Assessment context'):
        score_ribbon(snap)
        missing=snap.get('missing_inputs',[])
        if missing:st.write('Not recorded: '+', '.join(str(x).replace('_',' ') for x in missing))
    left,right=st.columns(2)
    with left:
        st.subheader('Original AI draft');st.markdown(r.get('ai_text') or 'No draft')
    with right:
        if r['status']=='Pending':
            with st.form('review_form_'+str(pick)):
                st.subheader('Your recommendation')
                revised=st.text_area('Revised recommendation',value=r.get('ai_text') or '',height=290,max_chars=12000)
                reason=st.text_area('Reason / coach note',max_chars=12000)
                approve=st.form_submit_button('Approve & send',type='primary');modify=st.form_submit_button('Edit & send');reject=st.form_submit_button('Reject with reason')
            if approve or modify or reject:
                decision='Approved' if approve else 'Modified' if modify else 'Rejected'
                review_recommendation(st.session_state.user_id,pick,decision,reason if not modify else revised);st.success('Saved and athlete notified.');st.rerun()
        else:st.subheader(r['status']);st.markdown(r.get('final_text') or r.get('comment') or '');st.caption(str(r.get('reviewed_at')))
    st.button('Open athlete details',on_click=go,args=('Athlete Detail',str(r['athlete_id'])))

def timeline(aid):
    uploads=list_uploads(aid);review=get_reviews(aid);events=[]
    for u in uploads:
        events.append((u['uploaded_at'],'Activity saved',u['filename']))
    for r in review:
        if r.get('reviewed_at'):events.append((r['reviewed_at'],'Coach '+r['status'].lower(),f"Upload #{r['upload_id']}"))
    for when,title,desc in sorted(events,key=lambda x:str(x[0]),reverse=True):
        with st.container(border=True):st.markdown('**'+title+'**');st.caption(str(when));st.write(desc)
    if not events:st.info('No recorded events yet.')
    st.caption('Only persisted event timestamps are shown. Reading a page is not assumed to be a recorded event.')

def connections(roster):
    from database.connection_request_repository import get_incoming_connection_requests,get_sent_connection_requests,send_connection_request,respond_to_connection_request
    cid=str(st.session_state.user_id);incoming,sent,connected=st.tabs(['Received','Sent','Connected'])
    with incoming:
        requests=get_incoming_connection_requests('Coach',cid)
        if not requests:st.info('No pending requests.')
        for r in requests:
            with st.container(border=True):
                st.write(r['sender_name']+' · '+r['sender_id']);st.write(r.get('message') or '')
                a,b=st.columns(2)
                for c,label,decision in [(a,'Accept','Accepted'),(b,'Reject','Rejected')]:
                    if c.button(label,key=label+str(r['request_id'])):respond_to_connection_request(r['request_id'],'Coach',cid,decision);st.rerun()
    with sent:
        rows=get_sent_connection_requests('Coach',cid)
        if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        with st.form('send_request'):
            uid=st.text_input('Athlete username');message=st.text_area('Message (optional)',max_chars=1000)
            if st.form_submit_button('Send request'):send_connection_request('Coach',cid,uid,message);st.success('Request sent.');st.rerun()
    with connected:
        for r in roster:
            with st.expander(r['name']+' · '+str(r['athlete_id'])):
                st.warning('Disconnecting ends your access to this athlete and removes them from your teams. Their account and records remain.')
                confirm=st.checkbox('I want to disconnect this athlete',key='dc'+str(r['athlete_id']))
                if st.button('Disconnect',key='disconnect'+str(r['athlete_id']),disabled=not confirm):db.disconnect(r['athlete_id']);st.session_state.pop('coach_athlete',None);st.rerun()

def notifications(roster):
    import re
    from database.connection_request_repository import get_notifications,mark_notification_read,mark_all_notifications_read
    cid=str(st.session_state.user_id);notices=get_notifications('Coach',cid);unread=st.checkbox('Unread only')
    if st.button('Mark all read'):mark_all_notifications_read('Coach',cid);st.rerun()
    allowed={str(r['athlete_id']) for r in roster}
    for n in notices:
        if unread and n['is_read']:continue
        with st.container(border=True):
            st.markdown('**'+n['notification_type']+'**');st.caption(str(n['created_at']))
            match=re.search(r'for athlete (.*?), upload #(\d+)',n['message']);aid=match[1] if match else None
            if aid and aid not in allowed:st.write('An update from a former connection is no longer accessible.');continue
            st.write(n['message'])
            if st.button('View details',key='notice'+str(n['notification_id'])):
                mark_notification_read(n['notification_id'],'Coach',cid)
                if aid:go('Athlete Detail',aid,upload=int(match[2]));st.session_state.cs_detail_tab='Recommendations'
                else:go('Connections')
                st.rerun()

def profile_page():
    from database.coach_identity import my_details
    from authentication.session import logout_user
    p=db.profile();d=my_details();left,right=st.columns([2,1])
    with left:
        with st.form('coach_profile'):
            name=st.text_input('Full name',value=p['name']);email=st.text_input('Email',value=d.get('email',''))
            org=st.text_input('Organisation',value=d.get('organisation',''));specialties=st.text_input('Specialties',value=d.get('specialties',''))
            if st.form_submit_button('Save changes',type='primary'):db.save_profile(name,dict(d,email=email,organisation=org,specialties=specialties));st.session_state.coach_display_name=name;st.success('Profile saved.')
    with right:
        st.subheader('Account')
        st.button('Sign out',on_click=sign_out)
        with st.expander('Delete my profile'):
            st.warning('Permanently delete your coach login and profile. Connections and teams end. Athlete accounts and completed review records remain. This cannot be undone.')
            password=st.text_input('Current password',type='password');confirm=st.text_input('Type DELETE to confirm')
            if st.button('Permanently delete',disabled=confirm!='DELETE'):
                db.delete_profile(password,confirm);st.session_state.clear();st.session_state.account_deleted_notice=True;st.rerun()

def render():
    try:st.session_state.coach_display_name=db.profile()['name'] # Check existence on every rerun.
    except PermissionError:
        st.session_state.clear();st.rerun()
    except Exception as exc:
        from ui.coach_errors import show_coach_error
        show_coach_error(exc, 'account');return
    st.session_state.setdefault('coach_page','Dashboard');shell()
    with st.container(key='cs_page_'+st.session_state.coach_page.replace(' ','_')+'_'+str(st.session_state.get('coach_transition',0))):
        if st.session_state.coach_page!='Dashboard':st.button('← Back to studio',key='cs_back',on_click=go,args=('Dashboard',))
        try:
            page=st.session_state.coach_page
            roster=[] if page in ('Profile','Reviews') else db.roster()
            if page=='Dashboard':dashboard(roster)
            elif page=='Athletes':athletes(roster)
            elif page=='Teams':teams_page(roster)
            elif page=='Team Detail':team_detail(roster)
            elif page in ('Athlete Detail','Twin Summary'):athlete_detail(roster)
            elif page=='Connections':heading('Connections','Manage requests and access to athlete data.');connections(roster)
            elif page=='Profile':heading('My profile','Your coaching identity and account settings.');profile_page()
            elif page=='Notifications':heading('Notifications','Updates from your connected athletes.');notifications(roster)
            elif page=='Reviews':heading('Recommendation Reviews','Review each AI draft before sending feedback.');reviews(st.session_state.get('coach_athlete'))
            elif page=='Intelligence':
                heading('Intelligence','Prioritise review of recent estimates and incomplete evidence.');table_roster(sorted(roster,key=lambda r: {'High':0,'Medium':1,'Not assessed':2,'Low':3}[attention(r.get('snapshot'))]),'intelligence')
            else:
                heading(page,'Explore your connected athlete’s saved records.');aid=selected(roster)
                if aid:
                    if page=='History':history_page(aid)
                    elif page=='Timeline':timeline(aid)
                    elif page=='Visualisation':chart_history(aid)
                    elif page in ('Forecasting','Model Evaluation'):forecast(aid,page=='Model Evaluation')
        except (ValueError,PermissionError) as exc:st.warning(str(exc))
        except Exception as exc:
            from ui.coach_errors import show_coach_error
            show_coach_error(exc)
