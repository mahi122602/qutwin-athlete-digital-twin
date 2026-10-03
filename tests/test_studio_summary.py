from datetime import datetime, timezone
from ui.studio_summary import build_summary

NOW=datetime(2026,9,24,12,tzinfo=timezone.utc)
def upload(**snapshot):
    return {'id':8,'uploaded_at':'2026-09-24T10:00:00+00:00','has_draft':True,
            'ai_excerpt':'Saved AI advice.', 'snapshot':{'prediction_status':'research_estimate',**snapshot}}
def run(rows,generated='2026-09-24T11:00:00+00:00'):
    return {'generated_at':generated,'forecast_payload':rows}
def row(f=30,r=80,i=20,day='2026-09-25'):
    return {'Date':day,'Fatigue forecast':f,'Readiness forecast':r,'Injury-risk score':i,'Confidence':'Low'}
def group(result,level):return next(x['items'] for x in result['groups'] if x['level']==level)
def source(result,name):return [(g['level'],i) for g in result['groups'] for i in g['items'] if i['source'].startswith(name)]

def test_exactly_three_groups_and_unknowns_never_low():
    result=build_summary(None,[],now=NOW)
    assert [g['level'] for g in result['groups']]==['High','Medium','Low']
    assert all(not g['items'] for g in result['groups'])
    assert len(result['unavailable'])==2

def test_current_thresholds_and_zero():
    for value,level in [(0,'Low'),(39.99,'Low'),(40,'Medium'),(69.99,'Medium'),(70,'High'),(100,'High')]:
        assert source(build_summary(upload(fatigue_score=value),[],now=NOW),'Fatigue')[0][0]==level

def test_invalid_and_unsupported_current_estimates_do_not_get_bands():
    for value in [float('nan'),float('inf'),-1,101,True,None]:
        assert not source(build_summary(upload(fatigue_score=value),[],now=NOW),'Fatigue')
    u=upload(fatigue_score=99,injury_risk='High');u['snapshot']['prediction_status']='analysis_only'
    result=build_summary(u,[],now=NOW)
    assert not source(result,'Fatigue') and not source(result,'Injury')

def test_readiness_stays_context_without_displacing_injury():
    result=build_summary(upload(fatigue_score=80,injury_risk='High',readiness_score=20),[],now=NOW)
    assert 'Readiness context' in source(result,'Fatigue')[0][1]['detail']
    assert 'Readiness context' not in source(result,'Injury')[0][1]['detail']

def test_forecast_selects_worst_future_day_not_expired_peak():
    f=run([row(95,20,90,'2026-09-20'),row(),row(70,55,50,'2026-09-26')])
    item=source(build_summary(upload(),[],f,now=NOW),'Forecast')[0]
    assert item[0]=='Medium' and '26 Sep' in item[1]['title']
    assert item[1]['action']=='forecast' and item[1]['upload_id'] is None

def test_forecast_stale_unknown_and_expired_are_unassessed():
    for forecast in [run([row()], '2026-09-24T09:00:00Z'), run([row()], '2026-09-24T11:00:00'),run([row(day='2026-09-20')])]:
        result=build_summary(upload(),[],forecast,now=NOW)
        assert not source(result,'Forecast')
        assert result['unavailable']

def test_partial_forecast_cannot_create_low_from_missing_values():
    result=build_summary(upload(),[],run([{'Date':'2026-09-25','Fatigue forecast':10}]),now=NOW)
    assert not source(result,'Forecast')

def test_coach_declined_not_medical_risk_and_quote_comes_from_record():
    result=build_summary(upload(),[{'status':'Rejected','comment':'Please review the session.'}],now=NOW)
    level,item=source(result,'Coach')[0]
    assert level=='High' and 'not an injury diagnosis' in item['detail']
    assert item['quote']=='Please review the session.' and item['upload_id']=='8'

def test_approval_and_another_pending_review_both_visible():
    result=build_summary(upload(),[{'status':'Approved'},{'status':'Pending'}],now=NOW)
    assert source(result,'Coach')[0][0]=='Low'
    assert source(result,'Recommendation')[0][0]=='Medium'

def test_failure_is_not_all_clear():
    result=build_summary(None,[],errors=['uploads','reviews','forecast'],now=NOW)
    assert len(result['unavailable'])==3
    assert all(not g['items'] for g in result['groups'])


def test_theme_event_keeps_page_and_user_session():
    from streamlit.testing.v1 import AppTest
    code="""import streamlit as st
import sys,types
for name,attrs in {
 'database.athlete_repository':{'get_athlete_profile':lambda x:{'name':'Tina'}},
 'database.connection_request_repository':{'get_unread_notification_count':lambda *x:0},
 'database.studio_repository':{'get_studio_records':lambda x:([{'id':8,'snapshot':{}}],[]),'get_studio_forecast':lambda x:None},
}.items():
 m=types.ModuleType(name)
 for k,v in attrs.items():setattr(m,k,v)
 sys.modules[name]=m
from views.athlete import studio
st.session_state.setdefault('user_id','athlete57')
st.session_state.setdefault('logged_in',True)
st.session_state.setdefault('current_page','Athlete Home')
studio._studio=lambda **kwargs:{'nonce':'theme-change','action':'theme','theme':'dusk'}
studio.render_studio()
st.write(st.session_state.current_page)
"""
    app=AppTest.from_string(code).run()
    assert not app.exception
    assert app.session_state.current_page=='Athlete Home'
    assert app.session_state.studio_theme_athlete57=='dusk'
    assert app.session_state.logged_in
    app.run()
    assert not app.exception
