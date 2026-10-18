#!/usr/bin/python3
"""GTCombo current-service MPEG-TS bridge sharing the native audio recorder.

Uses nonblocking copies from the existing audio DVR reader. No CA operations,
software filtering, extra DVR readers, or sysfs routing writes.
"""
import fcntl
import json
import os
import re
import select
import socket
import struct
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOCK = threading.Lock()
BASE = Path('/sys/class/stb')
PARAMS = Path('/sys/module/aml_hardware_dmx/parameters')


def current():
    with urllib.request.urlopen('http://127.0.0.1/web/getcurrent', timeout=3) as r:
        service = ET.fromstring(r.read()).find('e2service')
    if service is None:
        raise ValueError('No current service')
    ref = service.findtext('e2servicereference', '').strip()
    if not re.fullmatch(r'1:0:[0-9A-Fa-f:]+:', ref):
        raise ValueError('Current service is not a DVB service')
    name = service.findtext('e2servicename', 'Current channel')
    pids = {0}
    for key in ('e2vpid', 'e2apid', 'e2pcrpid', 'e2pmtpid'):
        value = service.findtext(key, '')
        if value.isdecimal() and 0 < int(value) < 8191:
            pids.add(int(value))
    if len(pids) < 3:
        raise ValueError('Current service is not ready')
    return ref, name, pids, int(service.findtext('e2apid', '0'))


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def reply(self, body, content_type, disposition=None):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        if disposition:
            self.send_header('Content-Disposition', disposition)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path == '/health':
            self.reply(json.dumps({'status': 'ready', 'recorder': 'native-audio-tee',
                                   'software_filter': False}).encode(), 'application/json')
            return
        if url.path not in ('/stream.m3u', '/stream'):
            self.send_error(404)
            return
        try:
            ref, name, pids, apid = current()
        except Exception:
            self.send_error(503, 'Tune a DVB channel on the receiver first')
            return
        wanted = q.get('ref', [ref])[0]
        if not re.fullmatch(r'1:0:[0-9A-Fa-f:]+:', wanted):
            self.send_error(400, 'Invalid DVB service reference')
            return
        if url.path == '/stream.m3u':
            title = q.get('name', [name if wanted == ref else 'channel'])[0]
            title = ' '.join(title.split())[:128] or 'channel'
            host = self.headers.get('Host', '')
            if not re.fullmatch(r'[A-Za-z0-9.-]+:8002', host):
                self.send_error(400, 'Invalid receiver address')
                return
            sid = int(wanted.split(':')[3], 16)
            target = 'http://' + host + '/stream?' + urllib.parse.urlencode({'ref': wanted})
            body = ('#EXTM3U\n#EXTVLCOPT:http-reconnect=true\n'
                    '#EXTINF:-1,%s\n#EXTVLCOPT:program=%d\n%s\n' %
                    (title, sid, target)).encode('utf-8')
            filename = re.sub(r'[\x00-\x1f\x7f/\\:*?"<>|]', '_', title).rstrip('. ') or 'channel'
            encoded = urllib.parse.quote(filename + '.m3u', safe='')
            fallback = re.sub(r'[^A-Za-z0-9 ._-]', '_', filename) or 'channel'
            disposition = 'attachment; filename="%s.m3u"; filename*=UTF-8\'\'%s' % (fallback, encoded)
            self.reply(body, 'audio/x-mpegurl; charset=utf-8', disposition)
            return
        if wanted != ref:
            self.send_error(409, 'Tune the requested channel on the receiver first')
            return
        if not LOCK.acquire(False):
            self.send_error(503, 'One current-channel stream is already active')
            return
        fds = []
        receiver = None
        bound = False
        sent = 0
        lost = 0
        cc = {}
        endpoint = '/run/gt-native-ts.sock'
        try:
            # Only the HTTP bridge owns this receive endpoint. The native
            # audio reader sends nonblocking copies and never depends on us.
            receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
            receiver.settimeout(4)
            if os.path.exists(endpoint):
                os.unlink(endpoint)
            receiver.bind(endpoint)
            bound = True
            os.chmod(endpoint, 0o600)
            first = receiver.recv(188 * 1024 + 8)
            if len(first) < 8 or first[:7] != b'GTTS\0\0\0' or first[7] not in (0, 1):
                raise ValueError('Invalid native recorder message')
            index = first[7]
            # DVR0 is the existing local CA playback recorder. Amlogic
            # leaves scrambling bits set after hardware descrambling here.
            # Never apply this correction to the raw TS1/DMX2 recorder.
            normalize = index == 0
            if normalize and not any(
                (BASE / ('dsc%d_source' % n)).read_text().strip() == 'dmx0-dmx0'
                for n in (0, 1)
            ):
                raise ValueError('Local CA recorder route is not active')
            if current()[0] != ref:
                raise ValueError('Service changed before recorder setup')
            # Audio already owns its PID filter and the sole DVR reader.
            # Add only the other PIDs to that same supported recording tap.
            for pid in sorted(pids - {apid}):
                dmx = os.open('/dev/dvb/adapter0/demux%d' % index, os.O_RDWR | os.O_NONBLOCK)
                fds.append(dmx)
                fcntl.ioctl(dmx, 0x40146f2c, struct.pack('H2xIIII', pid, 0, 2, 20, 4))
            self.connection.settimeout(5)
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp2t')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            held = b''
            check = time.monotonic() + 2
            while True:
                now = time.monotonic()
                if now > check:
                    if current()[0] != ref:
                        break
                    check = now + 2
                message = receiver.recv(188 * 1024 + 8)
                if len(message) < 8 or message[:7] != b'GTTS\0\0\0' or message[7] != index:
                    break
                held += message[8:]
                out = bytearray()
                pos = 0
                while len(held) - pos >= 188 * 3:
                    if held[pos] == 71 and held[pos+188] == 71 and held[pos+376] == 71:
                        packet = bytearray(held[pos:pos+188])
                        pos += 188
                        pid = ((packet[1] & 31) << 8) | packet[2]
                        if pid in pids:
                            if packet[3] & 16:
                                value = packet[3] & 15
                                if pid in cc and value not in (cc[pid], (cc[pid]+1) & 15):
                                    lost += 1
                                cc[pid] = value
                            if normalize:
                                packet[3] &= 63
                            out += packet
                    else:
                        pos += 1
                held = held[pos:]
                if out:
                    self.wfile.write(out)
                    sent += len(out)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass
        except Exception as exc:
            print('STREAM ERROR', type(exc).__name__, str(exc), flush=True)
        finally:
            for fd in reversed(fds):
                os.close(fd)
            if receiver is not None:
                receiver.close()
            if bound:
                os.unlink(endpoint)
            LOCK.release()
            self.close_connection = True
            print('STREAM END', ref, 'bytes', sent, 'continuity_errors', lost, flush=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    print('GT network stream ready: port 8002, shared native recorder', flush=True)
    Server(('0.0.0.0', 8002), Handler).serve_forever()
