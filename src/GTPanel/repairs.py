"""Declarative repair checks. Catalogs never execute installer scripts."""
import hashlib, json, os, struct, zlib
from .core import SafetyError
DEFAULT_ROOTS = ('/usr/lib/gtcombo/', '/etc/init.d/',
                 '/usr/lib/enigma2/python/Components/', '/usr/lib/enigma2/python/Screens/')
POLICY='/etc/gt-panel/policy.json'
PROTECTED=('/usr/lib/enigma2/python/Plugins/Extensions/GTPanel', '/etc/gt-panel',
           '/etc/passwd','/etc/shadow','/etc/group','/etc/gshadow','/etc/sudoers')

def roots():
    if not os.path.exists(POLICY): return DEFAULT_ROOTS
    with open(POLICY) as f: doc=json.load(f)
    configured=doc.get('repair_roots',list(DEFAULT_ROOTS))
    if not isinstance(configured,list) or not all(isinstance(p,str) and p.startswith(('/etc/','/usr/')) and p.endswith('/') and '..' not in p.split('/') for p in configured):
        raise SafetyError('Invalid local repair path policy')
    return tuple(configured)

def allowed(path):
    if any(path==p or path.startswith(p+'/') for p in PROTECTED):return False
    return any(path.startswith(p) and path!=p[:-1] for p in roots())

def validate(item):
    if item.get('action','files') not in ('files','repair'):raise SafetyError('Unsupported action: update GT Panel engine only for new action types')
    if item.get('action')!='repair':return
    if item.get('min_engine')!=2:raise SafetyError('Repair requires min_engine 2')
    inventory=item.get('targets')
    if not isinstance(inventory,dict) or set(inventory)!=set(item['files']):raise SafetyError('Repair targets do not match file inventory')
    for path,meta in inventory.items():
        if not isinstance(meta,dict) or not isinstance(meta.get('before'),list) or not meta['before']:raise SafetyError('Repair requires explicit old hashes or null for absent file')
        if not all(v is None or (isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v)) for v in meta['before']):raise SafetyError('Invalid old file hash')
        if not isinstance(meta.get('sha256'),str) or len(meta['sha256'])!=64 or any(c not in '0123456789abcdef' for c in meta['sha256']):raise SafetyError('Invalid new file hash')
        if type(meta.get('mode')) is not int or meta['mode'] not in (0o644,0o755):raise SafetyError('Only 0644 and 0755 target modes permitted')
    checks=item.get('checks',[])
    if not isinstance(checks,list) or len(checks)>20:raise SafetyError('Invalid repair checks')
    for check in checks:
        if check.get('type') not in ('sha256','uboot_env'):raise SafetyError('Unknown declarative check')
        path=check.get('path','')
        if not isinstance(path,str) or not path.startswith(('/etc/','/usr/','/proc/device-tree/','/sys/firmware/devicetree/','/dev/')) or '..' in path.split('/'):raise SafetyError('Invalid check path')
        size=check.get('bytes')
        if type(size) is not int or not 4<size<=4194304:raise SafetyError('Invalid bounded check size')
        if check['type']=='sha256' and (not isinstance(check.get('sha256'),str) or len(check['sha256'])!=64):raise SafetyError('Invalid check digest')
        if check['type']=='uboot_env':
            if check.get('data_offset') not in (4,5) or check.get('byteorder') not in ('little','big') or not isinstance(check.get('values'),dict):raise SafetyError('Invalid environment check')

def preflight(item,payload=None):
    validate(item)
    if item.get('action')!='repair':return
    from . import core
    if not core.compatible(item,core.facts()):raise SafetyError('Device identity changed or repair incompatible')
    for path,meta in item['targets'].items():
        core.safe_path(path,True)
        if os.path.exists(path):
            if not os.path.isfile(path):raise SafetyError('Non-regular target')
            with open(path,'rb') as f:
                data=f.read(32*1024*1024+1)
            if len(data)>32*1024*1024:raise SafetyError('Existing file too large')
            old=hashlib.sha256(data).hexdigest()
        else:old=None
        # Reapplying an identical payload is safe; changed unknown local files are not.
        if old not in meta['before'] and old!=meta['sha256']:raise SafetyError('Unreviewed local file: '+path)
        if payload is not None and hashlib.sha256(payload[path]).hexdigest()!=meta['sha256']:raise SafetyError('Per-file hash mismatch: '+path)
    for check in item.get('checks',[]):
        with open(check['path'],'rb',buffering=0) as f: data=f.read(check['bytes'])
        if len(data)!=check['bytes']:raise SafetyError('Short compatibility check read')
        if check['type']=='sha256':
            if hashlib.sha256(data).hexdigest()!=check['sha256']:raise SafetyError('Hardware/bootloader digest mismatch')
        else:
            offset=check['data_offset']; expected=int.from_bytes(data[:4],check['byteorder'])
            if zlib.crc32(data[offset:])&0xffffffff!=expected:raise SafetyError('Environment CRC invalid; no files installed')
            end=data.find(b'\0\0',offset)
            if end<0:raise SafetyError('Environment terminator missing')
            values={}
            for entry in data[offset:end].split(b'\0'):
                if b'=' not in entry:raise SafetyError('Malformed environment')
                k,v=entry.split(b'=',1)
                if k in values:raise SafetyError('Duplicate environment key')
                values[k]=v
            for k,v in check['values'].items():
                if values.get(k.encode())!=v.encode():raise SafetyError('Unexpected boot environment value: '+k)
