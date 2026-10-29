"""Reversible unknown-scancode trial. Never overwrite an existing mapping."""
import fcntl
import glob
import json
import os
from pathlib import Path
import struct
import tempfile

STATE=Path('/etc/enigma2/addremote-diagnostic/keymap-test.json')

def get_key(fd,scan):
    b=bytearray(struct.pack('=II',scan,0));fcntl.ioctl(fd,0x80084504,b,True)
    return struct.unpack('=II',b)[1]

def set_key(fd,scan,key):
    fcntl.ioctl(fd,0x40084504,struct.pack('=II',scan,key))
    if get_key(fd,scan)!=key:raise OSError('Keymap readback failed')

def identity(node):
    base=Path('/sys/class/input')/Path(node).name/'device'
    return {name:(base/name).read_text().strip() for name in ('name','phys','id/bustype','id/vendor','id/product')}

def journal(data):
    STATE.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd,path=tempfile.mkstemp(dir=STATE.parent,prefix='.trial-')
    try:
        with os.fdopen(fd,'w') as f:json.dump(data,f);f.flush();os.fsync(f.fileno())
        os.replace(path,STATE)
    finally:
        if os.path.exists(path):os.unlink(path)

def recover():
    if not STATE.exists():return
    data=json.loads(STATE.read_text())
    if not data:
        return
    if data.get('old')!=0 or data.get('key')!=108 or not isinstance(data.get('scan'),int) or not 0<=data['scan']<=0xffffffff:
        raise ValueError('Invalid trial recovery journal')
    matches=[]
    for node in glob.glob('/dev/input/event[0-9]*'):
        try:
            if identity(node)==data['identity']:matches.append(node)
        except OSError:pass
    if len(matches)!=1:raise OSError('Trial receiver missing or ambiguous; recovery pending')
    fd=os.open(matches[0],os.O_RDONLY|os.O_NONBLOCK)
    try:
        current=get_key(fd,data['scan'])
        if current==data['key']:set_key(fd,data['scan'],0)
        # Do not overwrite a later mapping owned by another component.
    finally:os.close(fd)
    journal({})

class MappingTrial:
    def __init__(self,action):
        self.action=action;self.callback=None;self.active=False
        self.result={'status':'not attempted','enigma_events':[]}

    def start(self,folder):
        recover()
        events=[json.loads(x) for x in (Path(folder)/'events.jsonl').read_text().splitlines()]
        originals={(e['device'],e['value']&0xffffffff) for e in events if e['phase'].startswith('original') and e['type']==4 and e['code']==4}
        counts={}
        for e in events:
            if e['phase']=='new_single' and e['type']==4 and e['code']==4:
                key=(e['device'],e['value']&0xffffffff);counts[key]=counts.get(key,0)+1
        for (node,scan),count in sorted(counts.items(),key=lambda x:x[1],reverse=True):
            if count<2 or (node,scan) in originals:continue
            fd=os.open(node,os.O_RDONLY|os.O_NONBLOCK)
            try:
                if get_key(fd,scan)!=0:continue
                data={'identity':identity(node),'scan':scan,'old':0,'key':108}
                journal(data)
                self.active=True
                def callback(key,flag):
                    if key==108:
                        self.result['enigma_events'].append({'key':key,'flag':flag})
                        return 1  # consume trial Down, so it does not change channels or selection
                    return 0
                self.callback=callback
                self.action.bindAction('',-2147483647,self.callback)
                set_key(fd,scan,108)
                self.result.update(status='temporary mapping verified',device=node,scan_hex='%08x'%scan,target='KEY_DOWN',original_key=0)
                return True
            except Exception:
                self.close();raise
            finally:os.close(fd)
        self.result['status']='skipped: no confirmed unknown scancode; existing original mappings preserved'
        return False

    def close(self):
        try:
            if self.active:recover();self.active=False;self.result['restored']=True
        finally:
            if self.callback:
                self.action.unbindAction('',self.callback);self.callback=None
        if self.result['enigma_events']:
            self.result['enigma_delivery']='observed'
        else:self.result['enigma_delivery']='not observed / not tested'
