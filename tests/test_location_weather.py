import pandas as pd
from services import activity_weather as w

def test_coordinates_validate():
    assert w.coordinates(0,0)==(0,0)
    for point in [(91,0),(0,181),(float('nan'),1),(None,0)]:
        assert w.coordinates(*point) is None

def test_missing_metadata_never_requests_weather(monkeypatch):
    monkeypatch.setattr(w,'hourly_weather',lambda *a: (_ for _ in ()).throw(AssertionError('No network expected')))
    assert w.weather_context({}, {},'Outdoor')['status']=='missing_location'
    assert w.weather_context({}, {'latitude':0,'longitude':0},'Outdoor')['status']=='missing_date'
    assert w.weather_context({}, {},'Indoor')['status']=='skipped'

def test_weather_uses_gps_and_weights_session(monkeypatch):
    calls=[]
    def hourly(*args):
        calls.append(args)
        return {'time':['2026-01-01T10:00','2026-01-01T11:00'],'temperature_2m':[20,30],'relative_humidity_2m':[40,60]},'Test weather'
    monkeypatch.setattr(w,'hourly_weather',hourly)
    r=w.weather_context({'latitude':1,'longitude':2,'timestamp':'2026-01-01T10:30Z','duration_minutes':90},
                        {'latitude':4,'longitude':5},'Outdoor',now='2026-02-01T00:00Z')
    assert r['temperature']==26.67 and r['humidity']==53.33
    assert calls[0][:2]==(1,2)
    assert r['estimated'] and not r['used_in_numeric_model']

def test_weather_outage_does_not_block(monkeypatch):
    monkeypatch.setattr(w,'hourly_weather',lambda *a: (_ for _ in ()).throw(TimeoutError()))
    r=w.weather_context({'timestamp':'2026-01-01T12:00Z'}, {'latitude':0,'longitude':0},'Outdoor')
    assert r['status']=='unavailable'

def test_daily_date_never_invents_timestamp(monkeypatch):
    frame=pd.DataFrame([{'heart_rate':140,'timestamp':None}])
    result=w.activity_details(frame,{'date':'2026-01-01','timezone':'UTC'})
    assert pd.isna(result.iloc[0]['timestamp'])
    assert result.iloc[0]['activity_date_only']=='2026-01-01'
    times=pd.date_range('2026-01-01',periods=24,freq='h').astype(str).tolist()
    monkeypatch.setattr(w,'hourly_weather',lambda *a:({'time':times,'temperature_2m':[20]*24,'relative_humidity_2m':[50]*24},'Test'))
    out=w.weather_context(result.iloc[0].to_dict(),{'latitude':0,'longitude':0},'Outdoor')
    assert out['temperature']==20 and 'Daily' in out['resolution']

def test_manual_date_never_overwrites_or_spreads():
    details={'timestamp':'2026-01-01T12:00Z'}
    original=pd.DataFrame([{'timestamp':'2025-01-01T12:00Z'}])
    assert w.activity_details(original,details).equals(original)
    many=pd.DataFrame([{'timestamp':None},{'timestamp':None}])
    assert w.activity_details(many,details).timestamp.isna().all()

def test_future_never_used(monkeypatch):
    r=w.weather_context({'timestamp':'2099-01-01T10:00Z'}, {'latitude':0,'longitude':0},'Outdoor')
    assert r['status']=='future'

def test_planned_events_do_not_relabel_cycling_or_multiply_load(monkeypatch):
    import prediction.upload_processing as p
    captured=[]
    monkeypatch.setattr(p,'list_uploads',lambda _:[])
    monkeypatch.setattr(p,'save_upload',lambda *args:captured.append(args) or {'status':'saved','id':1})
    entry={'df':pd.DataFrame([{'activity_type':'Cycling','training_load':35,'timestamp':None}]),
           'name':'bike.csv','digest':'hash','detection':{},'assignments':[],'planned_events_only':True}
    p.process_upload('a',entry,['100 m','200 m','400 m'])
    frame,snapshot=captured[0][4:6]
    assert frame.iloc[0]['activity_type']=='Cycling'
    assert frame.iloc[0]['event_type']=='Unknown'
    assert snapshot['training_load']==35
    assert snapshot['planned_event_count']==3
    assert captured[0][7]==[]

def test_gps_columns_survive_import():
    from ingestion.adaptive_table import normalise_table
    frame,_=normalise_table(pd.DataFrame([{'lat':0,'lon':12,'heart_rate':150}]))
    assert frame.iloc[0].latitude==0 and frame.iloc[0].longitude==12

def test_simple_page_saves_without_assignments(monkeypatch):
    import io
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    import views.athlete.upload as page
    class Upload(io.BytesIO):
        name='bike.csv'
    upload=Upload(b'activity_type,heart_rate,duration_minutes\nCycling,140,30\n')
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:[upload])
    monkeypatch.setattr(page,'location_settings',lambda _: ({},'Unknown'))
    calls=[]
    monkeypatch.setattr(page,'process_upload',lambda *args:calls.append(args) or {'status':'saved','id':5})
    app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='a'\nfrom views.athlete.upload import upload_garmin_data\nupload_garmin_data()").run()
    app.multiselect[0].select('100 m').select('400 m').run()
    assert not app.exception
    assert [x.value for x in app.subheader]==['1. Choose your events','2. Upload your data','3. Review and upload']
    assert not any(x.label=='Event assignment' for x in app.selectbox)
    next(b for b in app.button if b.label=='Upload and proceed').click().run()
    assert not app.exception and len(calls)==1
    assert calls[0][1]['assignments']==[]
    assert calls[0][2]==['100 m','400 m']

def test_prediction_keeps_automatic_drafts(monkeypatch):
    import views.athlete.predictions as page
    from streamlit.testing.v1 import AppTest
    upload=dict(id=1,uploaded_at='2026-09-23',filename='bike.csv',events=['400 m'],
                snapshot={'model_version':'adaptive-v2'},ai_text=None)
    calls=[]
    monkeypatch.setattr(page,'list_uploads',lambda _: [upload.copy()])
    monkeypatch.setattr(page,'get_reviews',lambda _: [])
    monkeypatch.setattr(page,'setting',lambda _: 'configured')
    def generate(*args):
        calls.append(args);upload['ai_text']='Generated draft'
    monkeypatch.setattr(page,'generate_for_upload',generate)
    app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='a'\nfrom views.athlete.predictions import athlete_predictions\nathlete_predictions()").run()
    assert not app.exception and not app.text_input and not app.button
    assert len(calls)==1
    app.run()
    assert len(calls)==1

def test_location_permission_component_is_click_only():
    from pathlib import Path
    code=Path('ui/location_component/index.html').read_text()
    assert 'onclick=function()' in code and 'getCurrentPosition' in code
    assert 'watchPosition' not in code
