from streamlit.testing.v1 import AppTest
import views.athlete.predictions as view

def page(monkeypatch, text=None, configured=True, reviews=None, pending=None):
    upload = dict(id=8, uploaded_at='2026-09-22', filename='run.csv',
                  events=['200 m'], snapshot={'model_version':'adaptive-v2'},
                  ai_text=text, ai_status='pending')
    calls=[]
    def generate(athlete, ident):
        calls.append(ident)
        upload.update(ai_text='Saved AI recommendation', ai_status='ready')
    monkeypatch.setattr(view, 'list_uploads', lambda _: [upload.copy()])
    monkeypatch.setattr(view, 'get_reviews', lambda _: reviews or [])
    monkeypatch.setattr(view, 'setting', lambda _: 'configured' if configured else '')
    monkeypatch.setattr(view, 'generate_for_upload', generate)
    app=AppTest.from_string("import streamlit as st\nst.session_state.user_id='a'\nfrom views.athlete.predictions import athlete_predictions\nathlete_predictions()")
    if pending: app.session_state['workflow_generate_ids']=pending
    app.run()
    assert not app.exception
    assert not app.text_input
    assert not app.button
    return app,calls

def test_missing_draft_automatic_and_persisted(monkeypatch):
    app,calls=page(monkeypatch)
    assert calls==[8]
    assert any(x.value=='Saved AI recommendation' for x in app.markdown)
    app.run()
    assert calls==[8]

def test_new_upload_batch_once(monkeypatch):
    app,calls=page(monkeypatch,pending=[8])
    assert calls==[8]

def test_existing_draft_needs_no_key(monkeypatch):
    app,calls=page(monkeypatch,text='Existing draft',configured=False)
    assert calls==[]
    assert any(x.value=='Existing draft' for x in app.markdown)

def test_no_config_no_setup_fields_or_empty_coach_section(monkeypatch):
    app,calls=page(monkeypatch,configured=False)
    assert calls==[]
    assert not any('coach' in x.value.lower() for x in app.subheader)
    assert any('temporarily unavailable' in x.value for x in app.info)

def test_review_displayed(monkeypatch):
    app,calls=page(monkeypatch,text='Draft',reviews=[
        dict(upload_id=8,coach_id='coach',status='Approved',final_text='Coach approved plan')])
    assert any(x.value=='Coach approved plan' for x in app.markdown)
