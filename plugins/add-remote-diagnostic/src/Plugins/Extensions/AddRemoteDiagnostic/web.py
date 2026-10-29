"""Local report downloads only; never serves arbitrary receiver paths."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit

PORT=6060
REPORT_ROOT=Path('/tmp')
PAGE='''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Add Remote Diagnostic</title><style>body{font:18px system-ui;background:#101722;color:#edf4f8;max-width:650px;margin:24px auto;padding:20px;line-height:1.8}h1{color:#28d4df;font-size:28px}.card{background:#1b2938;border-radius:20px;padding:20px;margin:16px 0}a,button{display:block;text-align:center;box-sizing:border-box;width:100%;border:0;border-radius:12px;padding:14px;margin:10px 0;background:#28d4df;color:#06161b;font:inherit;text-decoration:none}button:disabled{opacity:.5}.hint{color:#becbd6;font-size:16px}#message{color:#ffd588}</style><h1>تقارير فحص الريموت</h1><p>شغّل الفحص من شاشة التلفزيون؛ سيظهر التقرير هنا بعد انتهائه.</p><div id="reports" class="card">جارٍ البحث عن التقرير…</div><p id="message"></p><script>
const root=location.pathname;let latest=null;
async function refresh(){try{const r=await fetch(root+'api/reports',{cache:'no-store'});if(!r.ok)throw Error();const items=await r.json();document.getElementById('message').textContent='';const signature=JSON.stringify(items);if(signature===latest)return;latest=signature;const box=document.getElementById('reports');box.textContent='';if(!items.length){box.textContent='لا يوجد تقرير بعد. ابدأ الفحص من البلجن ثم انتظر اكتماله.';return;}for(const item of items){const c=document.createElement('section');c.className='card';const title=document.createElement('p');title.textContent=item.name;c.append(title);const a=document.createElement('a');a.href=root+'download/'+item.id;a.download=item.name;a.textContent='تنزيل التقرير';c.append(a);if(window.isSecureContext&&navigator.share&&navigator.canShare){const b=document.createElement('button');b.textContent='مشاركة الملف';b.onclick=async()=>{b.disabled=true;try{const r=await fetch(a.href);if(!r.ok)throw Error();const file=new File([await r.blob()],item.name,{type:'application/gzip'});if(!navigator.canShare({files:[file]}))throw Error('unsupported');b.disabled=false;b.textContent='الملف جاهز — اضغط لاختيار واتساب';b.onclick=async()=>{try{await navigator.share({files:[file]});}catch(e){if(e.name!=='AbortError')document.getElementById('message').textContent='نزّل الملف وشاركه من تطبيق الملفات.';}};}catch(e){b.disabled=false;document.getElementById('message').textContent='نزّل الملف وشاركه من تطبيق الملفات.';}};c.append(b);}box.append(c);}}catch(e){document.getElementById('message').textContent='تعذر الاتصال بالرسيفر. تأكد من اتصال الجوال بنفس الشبكة.';}}
refresh();setInterval(refresh,5000);
</script></html>'''

def local_addresses():
    """Read active IPv4 interface addresses without contacting an external host."""
    import fcntl
    import struct
    result=[]
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        for index,name in socket.if_nameindex():
            try:
                request=struct.pack('256s',name[:15].encode())
                addr=socket.inet_ntoa(fcntl.ioctl(sock.fileno(),0x8915,request)[20:24])
                if not ipaddress.ip_address(addr).is_loopback and addr not in result:result.append(addr)
            except OSError:pass
    return result

class ReportServer:
    def __init__(self,host='0.0.0.0',port=PORT):
        self.reports={};self.lock=threading.Lock()
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,code,body,kind='text/html; charset=utf-8',filename=None):
                self.send_response(code)
                self.send_header('Content-Type',kind)
                self.send_header('Content-Length',str(len(body)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Referrer-Policy','no-referrer')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
                if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
                self.end_headers();self.wfile.write(body)
            def do_GET(self):
                try:
                    address=ipaddress.ip_address(self.client_address[0])
                    if not (address.is_private or address.is_loopback):return self.reply(403,b'Local network only','text/plain')
                    path=urlsplit(self.path).path
                    suffix=path.lstrip('/')
                    if not suffix:return self.reply(200,PAGE.encode())
                    if suffix=='api/reports':
                        with owner.lock:items=[{'id':key,'name':p.name} for key,p in owner.reports.items() if p.is_file()]
                        return self.reply(200,json.dumps(items).encode(),'application/json')
                    if suffix.startswith('download/'):
                        key=suffix.removeprefix('download/')
                        with owner.lock:p=owner.reports.get(key)
                        if p is not None and p.is_file():return self.reply(200,p.read_bytes(),'application/gzip',p.name)
                    self.reply(404,b'Not found','text/plain')
                except (BrokenPipeError,ConnectionResetError):pass
                except OSError:self.reply(404,b'Report unavailable','text/plain')
        self.http=ThreadingHTTPServer((host,port),Handler)
        self.http.daemon_threads=True
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        # Restore completed reports after the GUI restarts, without rerunning IR capture.
        for report in sorted(REPORT_ROOT.glob('addremote-diagnostic-*.tar.gz'),key=lambda p:p.stat().st_mtime):
            try:self.publish(report)
            except (OSError,ValueError):pass

    def publish(self,path):
        p=Path(path).resolve()
        if p.parent!=REPORT_ROOT.resolve() or not p.name.startswith('addremote-diagnostic-') or not p.name.endswith('.tar.gz') or not p.is_file() or p.stat().st_size>2*1024*1024:
            raise ValueError('Not a generated diagnostic report')
        with self.lock:
            if p not in self.reports.values():self.reports[secrets.token_hex(8)]=p
            while len(self.reports)>10:del self.reports[next(iter(self.reports))]

    def close(self):
        self.http.shutdown();self.http.server_close();self.thread.join(timeout=2)

server=None

def ensure_server():
    global server
    if server is None:server=ReportServer()
    return server

def stop_server():
    global server
    if server is not None:server.close();server=None
