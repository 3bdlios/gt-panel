from __future__ import absolute_import
import os, sys, json, re, ssl, hashlib, tarfile, tempfile, shutil, time, stat
try:
    from urllib.request import urlopen, Request, HTTPRedirectHandler, build_opener, HTTPSHandler
    from urllib.parse import urlparse
except ImportError:
    from urllib2 import urlopen, Request, HTTPRedirectHandler, build_opener, HTTPSHandler
    from urlparse import urlparse

CATEGORIES = ('Fixes', 'Plugins', 'Skins', 'Updates')
BASE = '/usr/lib/enigma2/python/Plugins/Extensions/'
SKINS = '/usr/share/enigma2/'
STATE = '/var/lib/gt-panel'
class SafetyError(Exception): pass

def read(path):
    with open(path, 'r') as f: return f.read().strip()

def facts():
    # Hardware identity takes precedence over the donor image's dreamone metadata.
    model = None
    for path in ('/proc/device-tree/model', '/sys/firmware/devicetree/base/model', '/proc/stb/info/model'):
        try:
            value = read(path).strip('\x00 \t\r\n')
        except (IOError, OSError):
            continue
        if value:
            model = value
            break
    if not model:
        raise SafetyError('Hardware identity unavailable; installation blocked')
    try:
        metadata = dict(line.split('=', 1) for line in read('/etc/image-version').splitlines()
                        if '=' in line and not line.lstrip().startswith('#'))
    except (IOError, OSError):
        raise SafetyError('Image identity unavailable; installation blocked')
    distro = metadata.get('distro', '').strip()
    version = metadata.get('imageversion', '').strip()
    build = metadata.get('imagebuild', '').strip()
    if not distro or not version or not build:
        raise SafetyError('Incomplete image identity; installation blocked')
    return {'model': model, 'image': distro, 'version': version + '.' + build,
            'python': '%s.%s' % sys.version_info[:2]}

def github_url(url, repo, manifest=False):
    if not re.match(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$', repo): raise SafetyError('Invalid repository')
    p = urlparse(url)
    prefix = '/' + repo + '/'
    if p.scheme != 'https' or p.username or p.password or p.port or p.query or p.fragment:
        raise SafetyError('Only plain HTTPS GitHub URLs permitted')
    if p.hostname == 'raw.githubusercontent.com' and p.path.startswith(prefix): return
    if not manifest and p.hostname == 'github.com' and p.path.startswith(prefix + 'releases/download/'): return
    raise SafetyError('URL outside configured GitHub repository')

class Redirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urlparse(newurl)
        if p.scheme != 'https' or p.hostname not in ('release-assets.githubusercontent.com', 'github.com', 'raw.githubusercontent.com'):
            raise SafetyError('Rejected download redirect')
        return HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)

def fetch(url, repo, limit, manifest=False):
    github_url(url, repo, manifest)
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), Redirect())
    response = opener.open(Request(url, headers={'User-Agent':'GT-Panel/1.0'}), timeout=25)
    try:
        data = response.read(limit + 1)
        if len(data) > limit: raise SafetyError('Download too large')
        return data
    finally: response.close()

def validate(doc):
    if doc.get('schema') not in (1,2) or not isinstance(doc.get('items'), list) or len(doc['items']) > 100:
        raise SafetyError('Invalid manifest')
    ids = set()
    for i in doc['items']:
        if not re.match(r'^[a-z0-9][a-z0-9-]{0,63}$', i.get('id','')) or i['id'] in ids: raise SafetyError('Invalid/duplicate item id')
        ids.add(i['id'])
        if i.get('category') not in CATEGORIES: raise SafetyError('Invalid category')
        if not re.match(r'^[0-9a-f]{64}$', i.get('sha256','')): raise SafetyError('Missing SHA256')
        if type(i.get('size')) is not int or not 0 < i['size'] <= 16*1024*1024: raise SafetyError('Invalid size')
        if not isinstance(i.get('files'), list) or not 0 < len(i['files']) <= 200: raise SafetyError('Invalid file inventory')
        if len(set(i['files'])) != len(i['files']): raise SafetyError('Duplicate files')
        from . import repairs
        repairs.validate(i)
        for p in i['files']: safe_path(p, i.get('action')=='repair')
        for k in ('model','image','version','python'):
            if not isinstance(i.get('compatibility',{}).get(k), list) or not i['compatibility'][k]: raise SafetyError('Missing compatibility ' + k)
    return doc

def compatible(item, device):
    return all(device.get(k) in item['compatibility'][k] for k in ('model','image','version','python'))

def safe_path(path, repair=False):
    if not isinstance(path, str) or not path.startswith('/') or any(x in ('', '.', '..') for x in path.split('/')[1:]): raise SafetyError('Invalid path')
    # No core files, package managers, feeds, boot files or GT Panel self replacement.
    from . import repairs
    if any(path==p or path.startswith(p+'/') for p in repairs.PROTECTED): raise SafetyError('Protected target')
    if repair and repairs.allowed(path):
        pass
    elif path.startswith(BASE):
        name = path[len(BASE):].split('/')[0]
        if name == 'GTPanel' or '/' not in path[len(BASE):]: raise SafetyError('Protected plugin path')
    elif path.startswith(SKINS):
        if not path[len(SKINS):].startswith('GT-') or '/' not in path[len(SKINS):]: raise SafetyError('Only GT-* skin directories allowed')
    else: raise SafetyError('Path outside allowed plugin/skin directories')
    current = '/'
    for part in path.split('/')[1:]:
        current = os.path.join(current, part)
        if os.path.islink(current): raise SafetyError('Symlink in target path')
    return path

def prepare(item, repo, device):
    if not compatible(item, device): raise SafetyError('Item incompatible with local device identity')
    from . import repairs
    repairs.preflight(item)
    data = fetch(item['url'], repo, item['size'])
    if len(data) != item['size'] or hashlib.sha256(data).hexdigest() != item['sha256']: raise SafetyError('Hash/size mismatch')
    tmp = tempfile.mkdtemp(prefix='gt-panel-')
    try:
        archive = os.path.join(tmp, 'bundle.tar.gz')
        with open(archive,'wb') as f: f.write(data)
        payload = {}
        with tarfile.open(archive,'r:gz') as tf:
            total = 0
            for m in tf:
                path = '/' + m.name
                safe_path(path, item.get('action')=='repair')
                if not m.isfile() or m.mode & 0o7000 or path in payload: raise SafetyError('Unsafe archive member')
                total += m.size
                if total > 32*1024*1024: raise SafetyError('Expanded archive too large')
                payload[path] = tf.extractfile(m).read(32*1024*1024+1)
        if set(payload) != set(item['files']): raise SafetyError('Archive does not match declared file inventory')
        repairs.preflight(item,payload)
        return payload
    finally: shutil.rmtree(tmp)

def install(item, payload, confirmed=False):
    if confirmed is not True: raise SafetyError('Explicit confirmation required')
    if set(payload) != set(item['files']): raise SafetyError('Inventory changed')
    for p in payload: safe_path(p, item.get('action')=='repair')
    if not os.path.isdir(STATE): os.makedirs(STATE, 0o700)
    lock = os.path.join(STATE, 'install.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    backup = None
    try:
        from . import repairs
        repairs.preflight(item,payload)
        needed = sum(len(v) for v in payload.values()) * 3 + 1024*1024
        for root in (STATE, '/usr'):
            v = os.statvfs(root)
            if v.f_bavail*v.f_frsize < needed: raise SafetyError('Insufficient free space')
        backup = tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S-'), dir=STATE)
        journal = {'item':item['id'], 'files':[], 'status':'preparing', 'created_dirs':[], 'repair':item.get('action')=='repair'}
        for n, p in enumerate(sorted(payload)):
            exists = os.path.exists(p)
            if exists and not stat.S_ISREG(os.stat(p).st_mode): raise SafetyError('Target is not regular file')
            entry = {'path':p, 'backup':str(n) if exists else None, 'mode':stat.S_IMODE(os.stat(p).st_mode) if exists else 0o644}
            if exists:
                with open(p,'rb') as original: entry['sha256']=hashlib.sha256(original.read()).hexdigest()
                saved=os.path.join(backup,str(n)); shutil.copy2(p,saved)
                with open(saved,'rb') as copied:
                    if hashlib.sha256(copied.read()).hexdigest()!=entry['sha256']: raise SafetyError('Backup verification failed')
            journal['files'].append(entry)
        save_journal(backup, journal)
        try:
            for e in journal['files']:
                p = e['path']; safe_path(p, journal.get('repair',False))
                missing = []; parent = os.path.dirname(p)
                while not os.path.isdir(parent): missing.append(parent); parent = os.path.dirname(parent)
                for d in reversed(missing):
                    journal['created_dirs'].append(d); save_journal(backup,journal); os.mkdir(d,0o755)
                mode = item['targets'][p]['mode'] if item.get('action')=='repair' else e['mode']
                atomic(p, payload[p], mode)
            journal['status'] = 'installed'; save_journal(backup,journal)
        except Exception:
            _restore(backup); raise
        return backup
    finally: os.unlink(lock)

def atomic(path, data, mode):
    fd, temp = tempfile.mkstemp(prefix='.gt-panel-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(temp, mode); os.rename(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def save_journal(folder, journal):
    atomic(os.path.join(folder,'journal.json'), json.dumps(journal).encode('utf-8'),0o600)

def _restore(folder):
    j = json.loads(read(os.path.join(folder,'journal.json')))
    # Validate all saved files before restoring any target. Older journals may lack hashes.
    for e in j['files']:
        safe_path(e['path'], j.get('repair',False))
        if e['backup'] is not None:
            if not re.match(r'^\d+$',e['backup']): raise SafetyError('Invalid backup entry')
            with open(os.path.join(folder,e['backup']),'rb') as saved:
                if e.get('sha256') and hashlib.sha256(saved.read()).hexdigest()!=e['sha256']: raise SafetyError('Backup checksum mismatch; no targets restored')
    for e in reversed(j['files']):
        p = safe_path(e['path'], j.get('repair',False))
        if e['backup'] is None:
            if os.path.isfile(p): os.unlink(p)
        else:
            if not re.match(r'^\d+$',e['backup']): raise SafetyError('Invalid backup entry')
            with open(os.path.join(folder,e['backup']),'rb') as f: atomic(p,f.read(),e['mode'])
    for d in reversed(j.get('created_dirs',[])):
        safe_path(d + '/placeholder', j.get('repair',False))
        if os.path.isdir(d) and not os.listdir(d): os.rmdir(d)
    j['status']='restored'; save_journal(folder,j)


def restore(folder):
    if os.path.dirname(os.path.realpath(folder)) != os.path.realpath(STATE) or os.path.islink(folder):
        raise SafetyError('Backup outside state directory')
    lock = os.path.join(STATE, 'install.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try: return _restore(folder)
    finally: os.unlink(lock)
