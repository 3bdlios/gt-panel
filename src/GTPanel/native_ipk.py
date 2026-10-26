"""Engine-owned allowlist for two explicitly reviewed native IPKs.

Other catalog archives still use the declarative installer. This module does
not accept arbitrary package names, scripts, hashes or opkg arguments.
"""
import hashlib,json,os,platform,shutil,subprocess,tempfile,time
from .core import SafetyError
TRUSTED = {'xc-streamrelay-fix': {'sha256': '84bb06d7a7d2c037d7f1e35cfa9536587bdb3cb6dd4b3dd244170c5f1af6da97', 'size': 9590, 'filename': 'enigma2-plugin-systemplugins-xcstreamrelay_1.1.0_all.ipk', 'package': 'enigma2-plugin-systemplugins-xcstreamrelay', 'version': '1.1.0', 'files': ['/etc/gtcombo/native-streamrelay.enabled', '/usr/lib/enigma2/python/Plugins/SystemPlugins/GTNativeRelay/__init__.py', '/usr/lib/enigma2/python/Plugins/SystemPlugins/GTNativeRelay/plugin.py', '/usr/lib/gtcombo/gt-native-relay.py', '/usr/lib/gtcombo/libgt-relay-audio-input.so', '/usr/lib/gtcombo/xc-streamrelay-configure.py']}, 'xc-iptv-video-fix': {'sha256': '19a7d1a55c82b9e9697858a0aea81afc76ef06c707abaf1a82de56bff4cbe981', 'size': 7954, 'filename': 'enigma2-plugin-systemplugins-xcamlvideo_0.3.0_all.ipk', 'package': 'enigma2-plugin-systemplugins-xcamlvideo', 'version': '0.3.0', 'files': ['/usr/lib/gstreamer-1.0/libgstxcamlvideo.so']}}

def validate(item):
    spec=TRUSTED.get(item.get('id'))
    if spec is None: raise SafetyError('Native package is not reviewed by this engine')
    if item.get('action')!='native-ipk' or item.get('format')!='ipk' or item.get('min_engine')!=3 or item.get('category')!='Fixes':
        raise SafetyError('Invalid native package action')
    for k in ('sha256','size','version'):
        if item.get(k)!=spec[k]: raise SafetyError('Native package differs from reviewed release')
    if item.get('files')!=spec['files']: raise SafetyError('Native file inventory changed')
    expected={'model':['XCONN','GTMedia GT Combo'],'image':['openatv'],'version':['8.0.1.20261007'],'python':['3.14']}
    if item.get('compatibility')!=expected: raise SafetyError('Native compatibility changed')
    return spec

def verify(item,data):
    spec=validate(item)
    if not isinstance(data,bytes) or len(data)!=spec['size'] or hashlib.sha256(data).hexdigest()!=spec['sha256']:
        raise SafetyError('Native package hash/size mismatch')
    return spec

def prepare(item,repo,device):
    from . import core
    validate(item)
    if not core.compatible(item,device):raise SafetyError('Native package incompatible with receiver')
    data=core.fetch(item['url'],repo,item['size'])
    verify(item,data)
    return {'__reviewed_native_ipk__':data}

def install(item,payload,confirmed=False):
    from . import core
    if confirmed is not True:raise SafetyError('Installation requires confirmation')
    if not isinstance(payload,dict) or set(payload)!={'__reviewed_native_ipk__'}:raise SafetyError('Invalid native payload')
    data=payload['__reviewed_native_ipk__'];spec=verify(item,data)
    if platform.machine()!='aarch64' or not core.compatible(item,core.facts()):raise SafetyError('Native receiver identity changed')
    opkg=shutil.which('opkg')
    if opkg not in ('/usr/bin/opkg','/bin/opkg','/usr/sbin/opkg','/sbin/opkg'):raise SafetyError('Native package manager unavailable')
    os.makedirs(core.STATE,exist_ok=True)
    lock=os.path.join(core.STATE,'install.lock')
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise SafetyError('Another installation is running')
    os.close(fd)
    folder=None
    try:
        root=os.path.join(core.STATE,'native');os.makedirs(root,mode=0o700,exist_ok=True)
        folder=tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S')+'-'+item['id']+'-',dir=root)
        package=os.path.join(folder,spec['filename'])
        with open(package,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(package,0o600)
        log=os.path.join(folder,'install.log')
        record={'item':item['id'],'package':spec['package'],'version':spec['version'],'sha256':spec['sha256'],'status':'installing','backup':('/etc/xc-streamrelay-backups' if item['id']=='xc-streamrelay-fix' else '/etc/xc-amlvideo/original')}
        with open(log,'wb') as out:
            os.chmod(log,0o600)
            try:
                result=subprocess.run([opkg,'--force-reinstall','install',package],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=180,check=False)
            except subprocess.TimeoutExpired:
                record['status']='timeout';raise SafetyError('Native installation timed out; see '+log)
        if result.returncode:
            record['status']='failed';raise SafetyError('Native installation failed; see '+log)
        record['status']='installed'
        with open(os.path.join(folder,'native-install.json'),'w') as f:json.dump(record,f,indent=2)
        return record['backup']
    finally:
        if folder:
            for name in os.listdir(folder):
                if name.endswith('.ipk'):os.unlink(os.path.join(folder,name))
        os.unlink(lock)
