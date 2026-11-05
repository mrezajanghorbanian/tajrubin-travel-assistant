"""Loopback-only, in-memory browser test UI for the existing travel session."""
from __future__ import annotations
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from threading import Lock
import time

from app.assistant.local_model_session import LocalModelSession, SessionLimitError

WEB_ROOT=Path(__file__).with_name('web')
COOKIE='tajrubin_local'


class Entry:
    def __init__(self, factory):
        self.session=factory()
        self.csrf=secrets.token_urlsafe(32)
        self.history=[]
        self.touched=time.monotonic()
        self.lock=Lock()


class LocalChatServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self, port=8765, *, session_factory=None):
        self.entries={}
        self.entries_lock=Lock()
        self.inference_lock=Lock()
        self.session_factory=session_factory or (lambda:LocalModelSession(trip_state=True))
        super().__init__(('127.0.0.1',port),Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(150)

    def log_message(self,*args):
        pass  # No requests, prompts or cookies are written to disk.

    def reply(self,status,payload,*,mime='application/json; charset=utf-8',cookie=None):
        body=json.dumps(payload,ensure_ascii=False).encode('utf-8') if mime.startswith('application/json') else payload
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if cookie:self.send_header('Set-Cookie',f'{COOKIE}={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600')
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

    def entry(self,create=False):
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return None,None
        key=cookie[COOKIE].value if COOKIE in cookie else None
        with self.server.entries_lock:
            now=time.monotonic()
            expired=[k for k,v in self.server.entries.items() if now-v.touched>3600 and not v.lock.locked()]
            for k in expired:del self.server.entries[k]
            found=self.server.entries.get(key)
            if found is not None:
                found.touched=now
                return found,None
            if not create or len(self.server.entries)>=16:return None,None
            key=secrets.token_urlsafe(32)
            found=Entry(self.server.session_factory)
            self.server.entries[key]=found
            return found,key

    def snapshot(self,entry):
        return {'csrf':entry.csrf,'history':entry.history,'state':entry.session.trip_state.model_dump(mode='json'),'turns':len(entry.session.turns)}

    def do_GET(self):
        if not self.valid_host():return self.reply(403,{'error':'میزبان معتبر نیست.'})
        assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if self.path in assets:
            name,mime=assets[self.path]
            return self.reply(200,(WEB_ROOT/name).read_bytes(),mime=mime)
        if self.path!='/api/state':return self.reply(404,{'error':'مسیر موجود نیست.'})
        entry,key=self.entry(create=True)
        if entry is None:return self.reply(503,{'error':'ظرفیت جلسه‌ها پر است؛ بعداً دوباره تلاش کن.'})
        if not entry.lock.acquire(blocking=False):return self.reply(409,{'error':'این جلسه در حال پردازش است.'})
        try:self.reply(200,self.snapshot(entry),cookie=key)
        finally:entry.lock.release()

    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin')!=f"http://{self.headers.get('Host')}":
            return self.reply(403,{'error':'مبدأ درخواست معتبر نیست.'})
        if self.path not in {'/api/chat','/api/reset','/api/confirm'}:return self.reply(404,{'error':'مسیر موجود نیست.'})
        entry,_=self.entry()
        if entry is None or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),entry.csrf):
            return self.reply(403,{'error':'جلسه معتبر نیست؛ صفحه را تازه‌سازی کن.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=10000 or self.headers.get_content_type()!='application/json':raise ValueError()
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict):raise ValueError()
            if self.path=='/api/chat':
                if set(payload)!={'message'} or not isinstance(payload['message'],str) or not 3<=len(payload['message'].strip())<=2000:raise ValueError()
            elif payload:raise ValueError()
        except (ValueError,RecursionError):return self.reply(400,{'error':'ورودی معتبر نیست.'})
        if not entry.lock.acquire(blocking=False):return self.reply(409,{'error':'این جلسه در حال پردازش است.'})
        try:
            if self.path=='/api/reset':
                entry.session.reset();entry.history=[]
            elif self.path=='/api/confirm':
                result=entry.session.confirm_trip()
                text=result.feedback
                if result.question:text+='\n'+result.question
                entry.history.append({'role':'assistant','text':text})
            else:
                if not self.server.inference_lock.acquire(blocking=False):
                    return self.reply(429,{'error':'مدل مشغول پاسخ دیگری است؛ کمی بعد دوباره تلاش کن.'})
                try:result=entry.session.send(payload['message'])
                finally:self.server.inference_lock.release()
                if result.status!='model_reply':return self.reply(502,{'error':'مدل محلی پاسخ معتبر نداد. پیام ثبت نشد؛ دوباره تلاش کن.'})
                if result.state_status in {'rejected','not_applied'}:return self.reply(422,{'error':'تغییر اطلاعات تأیید نشد؛ جلسه قبلی حفظ شد.'})
                text=result.intake.understanding
                if result.knowledge is not None:
                    text+='\n\n'+result.knowledge.answer
                    for e in result.knowledge.evidence:
                        text+=f'\n[{e.document_id}] {e.document_title}'
                        if e.last_reviewed_at:text+='\nبازبینی: '+e.last_reviewed_at
                        for url in e.external_urls:text+='\n'+url
                if result.follow_up and result.follow_up.question:text+='\n\n'+result.follow_up.question
                entry.history.extend([{'role':'user','text':payload['message']},{'role':'assistant','text':text}])
            # UI transcript is bounded independently of the model transcript.
            entry.history=entry.history[-24:]
            self.reply(200,self.snapshot(entry))
        except SessionLimitError:self.reply(409,{'error':'ظرفیت این جلسه تست پر شده است. گفتگوی جدید بساز.'})
        except ValueError:self.reply(400,{'error':'ورودی قابل پردازش نیست؛ جلسه قبلی حفظ شد.'})
        finally:entry.lock.release()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Port must be between 1024 and 65535')
    with LocalChatServer(args.port) as server:
        print(f'Local travel chat: http://127.0.0.1:{server.server_port}',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass


if __name__=='__main__':main()
