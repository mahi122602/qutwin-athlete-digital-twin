from ui.studio_model import build_studio_model, resolve_action


def test_empty_and_missing_measurements_are_not_invented():
    m=build_studio_model({},[],[])
    assert not m['has_data']
    assert all(x['value']=='—' for x in m['measurements'])
    assert m['coach_route']=='requests'


def test_saved_date_is_not_activity_date_and_zero_is_valid():
    m=build_studio_model({'name':'Tina'},[{'id':8,'uploaded_at':'2026-09-22T12:00:00+10:00','snapshot':{'heart_rate':float('nan'),'calories':0},'events':['400 m']}],[])
    assert m['measurements'][0]['value']=='—'
    assert m['measurements'][2]['value']=='0'
    assert not m['activity_date_known']
    assert m['uploads'][0]['date'].startswith('Saved')
    assert m['events']==['400 m']


def test_coach_decision_and_draft_are_distinct():
    u=[{'id':8,'snapshot':{},'has_draft':True}]
    assert build_studio_model({},u,[])['coach_status']=='Draft ready'
    assert build_studio_model({},u,[{'status':'Pending'}])['coach_status']=='Awaiting review'
    assert build_studio_model({},u,[{'status':'Modified'}])['coach_status']=='Revised by coach'
    assert build_studio_model({},u,[{'status':'Rejected'}])['coach_status']=='Not approved'


def test_actions_cannot_target_another_athletes_upload():
    assert resolve_action({'nonce':'1','action':'activity','upload_id':9},[8]) is None
    assert resolve_action({'nonce':'1','action':'delete'},[8]) is None
    assert resolve_action({'nonce':'1','action':'activity','upload_id':'8'},[8])['page']=='Predictions & Coach Recommendations'


def test_database_error_is_not_presented_as_no_activities():
    m=build_studio_model({},[],[],errors=['uploads','reviews'])
    assert m['status']=='Connection interrupted'
    assert m['coach_status']=='Temporarily unavailable'


def test_prediction_selection_follows_studio_link():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    source=(Path(__file__).resolve().parents[1]/'views/athlete/predictions.py').read_text()
    start=source.index('        upload_ids =')
    end=source.index("        st.caption('Upcoming events:",start)
    import textwrap
    code="""import streamlit as st
athlete_id='test'
pending=[]
uploads=[{'id':8,'filename':'new.csv','uploaded_at':'today','snapshot':{}},{'id':7,'filename':'old.csv','uploaded_at':'yesterday','snapshot':{}}]
st.session_state.setdefault('studio_target_upload','7')
"""+textwrap.dedent(source[start:end])+"\nst.write(str(u['id']))"
    app=AppTest.from_string(code).run()
    assert not app.exception
    assert app.selectbox[0].value=='7'


def test_adapter_routes_once_without_losing_session():
    from streamlit.testing.v1 import AppTest
    code="""import streamlit as st
import sys,types
for name,attrs in {
 'database.athlete_repository':{'get_athlete_profile':lambda x:{'name':'Tina'}},
 'database.connection_request_repository':{'get_unread_notification_count':lambda *x:0},
 'database.studio_repository':{'get_studio_records':lambda x:([{'id':8,'snapshot':{}}],[])},
}.items():
 m=types.ModuleType(name)
 for k,v in attrs.items():setattr(m,k,v)
 sys.modules[name]=m
from views.athlete import studio
st.session_state.setdefault('user_id','athlete57')
st.session_state.setdefault('logged_in',True)
st.session_state.setdefault('current_page','Athlete Home')
studio._studio=lambda **kwargs:{'nonce':'same-event','action':'activity','upload_id':'8'}
studio.render_studio()
st.write(st.session_state.current_page)
"""
    app=AppTest.from_string(code).run()
    assert not app.exception
    assert app.session_state.current_page=='Predictions & Coach Recommendations'
    assert app.session_state.studio_target_upload=='8'
    assert app.session_state.logged_in
    app.run()
    assert not app.exception
