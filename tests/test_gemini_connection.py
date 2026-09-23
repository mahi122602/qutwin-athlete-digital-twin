"""Offline transport checks: no live keys or network calls."""
import io
import json
from urllib.error import HTTPError
import pytest
from recommendation import llm_service as llm
from ingestion import ai_mapping

def configure(monkeypatch):
    values={'GEMINI_API_KEY':'dummy-test-key','QUTWIN_GEMINI_MODEL':'gemini-2.5-flash-lite'}
    monkeypatch.setattr(llm,'setting',lambda name:values.get(name,''))

def test_recommendation_uses_google_and_preserves_workflow(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(llm,'claim_ai',lambda *a:({'snapshot':{'fatigue_score':40},'events':['200 m','800 m'],'records':[{}]},'token'))
    saved=[]
    monkeypatch.setattr(llm,'finish_ai',lambda *a,**k:saved.append(k))
    def respond(req,timeout):
        assert req.full_url=='https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent'
        assert req.get_header('X-goog-api-key')=='dummy-test-key'
        body=json.loads(req.data)
        assert 'systemInstruction' in body and 'messages' not in body
        assert json.loads(body['contents'][0]['parts'][0]['text'])['selected_events']==['200 m','800 m']
        return io.BytesIO(b'{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"Draft for coach review"}]}}]}')
    monkeypatch.setattr(llm,'urlopen',respond)
    llm.generate_for_upload('athlete',1)
    assert saved[0]['text']=='Draft for coach review'

@pytest.mark.parametrize('code',[400,401,403,404,429,503])
def test_google_errors_retained_without_secrets(monkeypatch,code):
    configure(monkeypatch)
    monkeypatch.setattr(llm,'claim_ai',lambda *a:({'snapshot':{},'events':[],'records':[]},'token'))
    saved=[]
    monkeypatch.setattr(llm,'finish_ai',lambda *a,**k:saved.append(k))
    def fail(*a,**k):raise HTTPError('https://example.invalid',code,'dummy-test-key',{},None)
    monkeypatch.setattr(llm,'urlopen',fail)
    llm.generate_for_upload('athlete',1)
    assert saved[0].get('error') and 'dummy-test-key' not in saved[0]['error']
    assert 'text' not in saved[0]

def test_header_mapping_uses_google(monkeypatch):
    configure(monkeypatch)
    def respond(req,timeout):
        assert req.full_url.startswith('https://generativelanguage.googleapis.com/')
        body=json.loads(req.data)
        assert body['generationConfig']=={'responseMimeType':'application/json'}
        payload={'fields':{'heart_rate':{'column':'Average HR','unit':None}}}
        return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(payload)}]}}]}).encode())
    monkeypatch.setattr(ai_mapping,'urlopen',respond)
    assert ai_mapping.suggest_columns(['Average HR'])['mapping']=={'heart_rate':'Average HR'}


def test_native_response_drops_thoughts_and_rejects_partial():
    from utils.gemini_native import response_text
    assert response_text({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'private thought','thought':True},{'text':'Draft'}]}}]})=='Draft'
    for payload in ({'promptFeedback':{'blockReason':'SAFETY'}},{'candidates':[]},{'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]}):
        with pytest.raises(ValueError):response_text(payload)

def test_native_error_keeps_reason_redacts_key():
    from utils.gemini_native import http_error
    key='dummy-secret'
    exc=HTTPError('https://example.invalid',400,'bad',{},io.BytesIO(json.dumps({'error':{'message':'API key not valid '+key}}).encode()))
    message=http_error(exc,key,'model')
    assert 'API key not valid' in message and key not in message
