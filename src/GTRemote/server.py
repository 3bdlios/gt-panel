#!/usr/bin/python3
"""Small LAN web remote; commands are forwarded to OpenWebif, never a shell."""
import argparse
import base64
import hashlib
import hmac
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).parent
STATE = Path('/var/lib/gt-remote/config.json')
KEYS = {2,3,4,5,6,7,8,9,10,11,412,407,398,399,400,401,139,103,174,
        105,352,106,358,108,365,115,113,402,114,388,403,168,207,119,208,
        165,167,128,163,392,370,393,366,377,385,138,141,156,142,359,
        59,60,364,375,158,357,438,373}


def config(path=STATE):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text())
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = {'port':8088, 'pin':str(secrets.randbelow(900000)+100000), 'secret':secrets.token_hex(32)}
    fd = os.open(str(path), os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd,'w') as target:
        json.dump(data,target)
    return data


def session_token(settings, timestamp=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = hmac.new(settings['secret'].encode(),timestamp.encode(),hashlib.sha256).hexdigest()
    return timestamp+'.'+signature


def valid_token(settings, token):
    try:
        stamp, signature = token.split('.',1)
        age = time.time()-int(stamp)
        return -300 <= age <= 86400 and hmac.compare_digest(session_token(settings,stamp),token)
    except (ValueError,TypeError):
        return False


class RemoteServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self,address,settings):
        self.settings=settings
        self.attempts={}
        self.lock=threading.Lock()
        self.key_lock=threading.Lock()
        super().__init__(address,Handler)


class Handler(BaseHTTPRequestHandler):
    server_version='GT-Remote/1.0'
    protocol_version='HTTP/1.0'

    def log_message(self,*args):
        pass

    def send(self,status,data,kind='application/json',extra=None):
        if isinstance(data,dict):data=json.dumps(data).encode()
        if isinstance(data,str):data=data.encode()
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for key,value in (extra or {}).items():self.send_header(key,value)
        self.end_headers()
        try:self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):pass

    def paired(self):
        jar=cookies.SimpleCookie()
        try:jar.load(self.headers.get('Cookie',''))
        except cookies.CookieError:return False
        return 'gtremote' in jar and valid_token(self.server.settings,jar['gtremote'].value)

    def local_origin(self):
        origin=self.headers.get('Origin')
        return (not origin or urllib.parse.urlparse(origin).netloc==self.headers.get('Host')) and self.headers.get('X-GT-Remote')=='1'

    def upstream(self,path,data=None):
        headers={}
        # Existing OpenWebif authentication remains authoritative, if enabled.
        if self.headers.get('Authorization'):headers['Authorization']=self.headers['Authorization']
        if data is not None:headers['Content-Type']='application/x-www-form-urlencoded'
        request=urllib.request.Request('http://127.0.0.1:80'+path,data=data,headers=headers)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request,timeout=3) as response:
                result=response.read(2*1024*1024+1)
                if len(result)>2*1024*1024:raise ValueError('Response too large')
                self.send(response.status,result,response.headers.get('Content-Type','application/json'))
        except urllib.error.HTTPError as error:
            extra={}
            if error.code==401:extra['WWW-Authenticate']=error.headers.get('WWW-Authenticate','Basic realm="OpenWebif"')
            self.send(error.code,{'error':'OpenWebif rejected the request'},extra=extra)
        except (OSError,ValueError,TimeoutError):
            self.send(502,{'error':'OpenWebif is not responding. Check that it is enabled on port 80.'})

    def do_GET(self):
        route=urllib.parse.urlparse(self.path).path
        assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','application/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if route in assets:
            name,kind=assets[route];return self.send(200,(ROOT/'web'/name).read_bytes(),kind)
        if route=='/api/status':
            return self.send(200,{'paired':self.paired(),'name':'GT Remote','port':self.server.settings['port']})
        if not self.paired():return self.send(401,{'error':'Pair this phone first'})
        if route=='/api/screenshot':return self.upstream('/grab?format=jpg&mode=osd&r=720')
        self.send(404,{'error':'Not found'})

    def do_POST(self):
        if not self.local_origin():return self.send(403,{'error':'Invalid origin'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=4096:raise ValueError()
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):raise ValueError()
        except (ValueError,UnicodeError):return self.send(400,{'error':'Invalid request'})
        route=urllib.parse.urlparse(self.path).path
        if route=='/api/pair':
            ip=self.client_address[0]
            with self.server.lock:
                now=time.monotonic()
                self.server.attempts={k:[t for t in values if now-t<60] for k,values in self.server.attempts.items() if values and now-values[-1]<60}
                tries=self.server.attempts.setdefault(ip,[])
                if len(tries)>=5:return self.send(429,{'error':'Wait one minute before trying again'})
                tries.append(now)
                if not hmac.compare_digest(str(data.get('pin','')),self.server.settings['pin']):return self.send(403,{'error':'Incorrect pairing code'})
                self.server.attempts.pop(ip,None)
            return self.send(200,{'result':True},extra={'Set-Cookie':'gtremote='+session_token(self.server.settings)+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'})
        if not self.paired():return self.send(401,{'error':'Pair this phone first'})
        if route=='/api/key':
            code=data.get('code')
            if type(code) is not int or code not in KEYS:return self.send(400,{'error':'Unknown remote key'})
            params={'command':code}
            if data.get('long') is True:params['type']='long'
            with self.server.key_lock:
                return self.upstream('/api/remotecontrol?'+urllib.parse.urlencode(params))
        if route=='/api/text':
            text=data.get('text','')
            if not isinstance(text,str) or not 1<=len(text)<=200:return self.send(400,{'error':'Text must be 1–200 characters'})
            return self.upstream('/api/remotecontrol?'+urllib.parse.urlencode({'text':text}))
        if route=='/api/message':
            text=data.get('text','')
            if not isinstance(text,str) or not 1<=len(text)<=200:return self.send(400,{'error':'Message must be 1–200 characters'})
            return self.upstream('/api/message?'+urllib.parse.urlencode({'text':text,'type':1,'timeout':6}))
        if route=='/api/power':
            # Standby/wakeup only. Restart/shutdown are not exposed by this page.
            if type(data.get('state')) is not int or data['state'] not in (0,4,5):return self.send(400,{'error':'Invalid power action'})
            return self.upstream('/api/powerstate?newstate='+str(data['state']))
        self.send(404,{'error':'Not found'})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',default=str(STATE));args=parser.parse_args()
    settings=config(args.config)
    # Follow Enigma2 lifetime, including an abnormal GUI exit.
    try:
        import ctypes,signal
        parent=os.getppid();ctypes.CDLL(None).prctl(1,signal.SIGTERM)
        if os.getppid()!=parent:raise SystemExit(0)
    except (ImportError,AttributeError):pass
    RemoteServer(('0.0.0.0',int(settings['port'])),settings).serve_forever()
