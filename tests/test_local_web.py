"""HTTP boundary tests with a real session and controlled model replies."""
import json
from threading import Thread
import httpx
import pytest
from app.assistant.local_web import LocalChatServer
from app.assistant.local_model_session import LocalModelSession
from app.providers.text_generation import TextGenerationResponseV1

class Provider:
    def generate(self,request):
        message=json.loads(request.prompt)['current_user']
        return TextGenerationResponseV1(text=json.dumps({'understanding':message,'clarification_question':None,'search':None,'updates':{'destination':'شیراز' if 'شیراز' in message else None,'duration':None,'dates':None,'party':None,'budget':None,'preferences':None}},ensure_ascii=False))

@pytest.fixture
def local():
    server=LocalChatServer(0,session_factory=lambda:LocalModelSession(trip_state=True,provider=Provider()))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    with httpx.Client(base_url=url,trust_env=False) as client:
        yield client,url,server
    server.shutdown();server.server_close();thread.join(3)

def connect(client,url):
    state=client.get('/api/state').json()
    return {'Origin':url,'X-CSRF-Token':state['csrf']}

def test_chat_confirm_reset_and_browser_isolation(local):
    client,url,server=local;headers=connect(client,url)
    r=client.post('/api/chat',headers=headers,json={'message':'سفر شیراز'})
    assert r.status_code==200 and r.json()['state']['destination']['value']=='شیراز'
    assert 'تاریخ' in r.json()['history'][-1]['text']
    assert client.post('/api/confirm',headers=headers,json={}).status_code==200
    with httpx.Client(base_url=url,trust_env=False) as other:
        assert other.get('/api/state').json()['state']['destination'] is None
    cleared=client.post('/api/reset',headers=headers,json={}).json()
    assert cleared['history']==[] and cleared['state']['destination'] is None

def test_cross_origin_csrf_host_and_path_boundaries(local):
    client,url,server=local;headers=connect(client,url)
    assert client.post('/api/chat',json={'message':'سفر شیراز'}).status_code==403
    assert client.post('/api/reset',headers={**headers,'Origin':'https://evil.example'},json={}).status_code==403
    assert client.post('/api/reset',headers={**headers,'X-CSRF-Token':'wrong'},json={}).status_code==403
    assert client.get('/',headers={'Host':'evil.example'}).status_code==403
    assert client.get('/../pyproject.toml').status_code==404
    assert client.get('/app.js').status_code==200
    page=client.get('/')
    assert 'frame-ancestors' in page.headers['content-security-policy']
    assert page.headers['cache-control']=='no-store'

@pytest.mark.parametrize('payload',[{'message':'x'},{'message':123},{'message':'a'*2001},{'message':'valid','tool':'book'},[]])
def test_invalid_http_input_does_not_advance_session(local,payload):
    client,url,server=local;headers=connect(client,url)
    assert client.post('/api/chat',headers=headers,json=payload).status_code==400
    assert client.get('/api/state').json()['turns']==0

def test_output_is_data_and_cookie_is_not_script_readable(local):
    client,url,server=local
    init=client.get('/api/state')
    assert 'HttpOnly' in init.headers['set-cookie'] and 'SameSite=Strict' in init.headers['set-cookie']
    headers={'Origin':url,'X-CSRF-Token':init.json()['csrf']}
    text='<script>alert(1)</script>'
    r=client.post('/api/chat',headers=headers,json={'message':text})
    assert r.status_code==200 and r.json()['history'][0]['text']==text
    script=client.get('/app.js').text
    assert 'innerHTML' not in script and 'textContent' in script
