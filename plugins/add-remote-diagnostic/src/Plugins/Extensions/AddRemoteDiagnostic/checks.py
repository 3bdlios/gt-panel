"""Read-only remote subsystem inventory and evidence-based event checks."""
import fcntl
import glob
import json
import os
from pathlib import Path
import struct
from .collector import read

PHASES=[('new_single',15,'الجديد فقط: اضغط الزر نفسه 3 مرات منفصلة.\nNEW: same button, 3 separate presses.'),
        ('new_hold',10,'الجديد فقط: علّق على الزر 4 ثوانٍ ثم حرره.\nNEW: hold 4 seconds, then release.'),
        ('new_buttons',20,'الجديد فقط: اضغط 3 أزرار مختلفة، بدون Power.\nNEW: press 3 different buttons, avoid Power.'),
        ('pause',5,'لا تضغط أي ريموت.\nPAUSE: do not press either remote.'),
        ('original_remote',15,'الأصلي فقط: سهم أسفل 3 مرات ثم سهم أعلى مرة.\nORIGINAL: DOWN 3 times, UP once.'),
        ('original_hold',10,'الأصلي فقط: علّق سهم أسفل 4 ثوانٍ ثم حرره.\nORIGINAL: hold DOWN 4 seconds, then release.')]


def inspect_devices(info):
    result={'input':[],'lirc':[],'bluetooth':[],'limits':[
        'Supported protocol names are driver declarations, not proof that every protocol was tested.',
        'No protocol filter, original keymap, pairing or driver is changed.',
        'Bluetooth checks cover existing HID devices only; no pairing, microphone or BLE GATT test.',
        'Raw LIRC timing availability does not prove that a remote can be decoded or mapped.']}
    for device in info['devices']:
        item={'node':device['node'],'name':device.get('name'),'phys':device.get('phys'),'tests':{}}
        fd=None
        try:
            fd=os.open(device['node'],os.O_RDONLY|os.O_NONBLOCK)
            for name,request,size,fmt in [('input_id',0x80084502,8,'=HHHH'),('repeat_ms',0x80084503,8,'=II'),('driver_version',0x80044501,4,'=I')]:
                b=bytearray(size)
                try:fcntl.ioctl(fd,request,b,True);item['tests'][name]={'status':'available','value':struct.unpack(fmt,b)}
                except OSError as e:item['tests'][name]={'status':'unavailable','reason':str(e)}
            mapping=[]
            for index in range(512):
                b=bytearray(struct.pack('=BBHI32s',1,0,index,0,b''))
                try:fcntl.ioctl(fd,0x80284504,b,True)
                except OSError as e:
                    item['keymap_status']='available' if mapping else 'unavailable: '+str(e)
                    break
                flags,length,idx,key,scan=struct.unpack('=BBHI32s',b)
                mapping.append({'index':idx,'scan':scan[:min(length,32)].hex(),'keycode':key})
            item['keymap']=mapping
            if len(mapping)==512:item['keymap_status']='available, limited to 512 entries'
            if str(device.get('id/bustype','')).strip()=='0005':result['bluetooth'].append({'node':device['node'],'name':device.get('name'),'status':'paired HID input visible'})
        except OSError as e:item['error']=str(e)
        finally:
            if fd is not None:os.close(fd)
        result['input'].append(item)
    for path in glob.glob('/dev/lirc[0-9]*'):
        item={'node':path};fd=None
        try:
            fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
            for name,request in [('features',0x80046900),('receive_mode',0x80046902)]:
                b=bytearray(4)
                try:fcntl.ioctl(fd,request,b,True);item[name]={'status':'available','value':struct.unpack('=I',b)[0]}
                except OSError as e:item[name]={'status':'unavailable','reason':str(e)}
        except OSError as e:item['error']=str(e)
        finally:
            if fd is not None:os.close(fd)
        result['lirc'].append(item)
    result['bluetooth_sysfs']=[{'node':p,'uevent':read(p+'/uevent',4096)} for p in glob.glob('/sys/class/bluetooth/hci[0-9]*')]
    return result


def evaluate(folder):
    by_phase={};devices={};previous={};deltas={}
    path=Path(folder)/'events.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            e=json.loads(line);phase=e['phase'];device=e['device'];p=by_phase.setdefault(phase,{'key_down':0,'key_up':0,'key_repeat':0,'scancodes':[],'keycodes':[]})
            d=devices.setdefault(device,{'key_events':0,'scan_events':0})
            if e['type']==4 and e['code']==4:
                scan=e['value']&0xffffffff
                if scan not in p['scancodes']:p['scancodes'].append(scan)
                d['scan_events']+=1
                k=(phase,device,scan)
                if k in previous:deltas.setdefault(phase,[]).append(round(e['monotonic']-previous[k],4))
                previous[k]=e['monotonic']
            if e['type']==1:
                d['key_events']+=1
                field={0:'key_up',1:'key_down',2:'key_repeat'}.get(e['value'])
                if field:p[field]+=1
                if e['code'] not in p['keycodes']:p['keycodes'].append(e['code'])
    new=[v for k,v in by_phase.items() if k.startswith('new_')]
    original=[v for k,v in by_phase.items() if k.startswith('original_')]
    def evidence(items):return any(x['scancodes'] or x['key_down'] for x in items)
    return {'phase_results':by_phase,'sources':devices,'repeat_frame_intervals_seconds':deltas,
            'new_remote_events':'observed' if evidence(new) else 'not observed; inconclusive',
            'original_remote_events':'observed' if evidence(original) else 'not observed; check capture visibility',
            'long_press_new':'EV_KEY repeat observed' if by_phase.get('new_hold',{}).get('key_repeat') else 'no EV_KEY repeat observed; inspect scan timings',
            'long_press_original':'EV_KEY repeat observed' if by_phase.get('original_hold',{}).get('key_repeat') else 'no EV_KEY repeat observed',
            'new_release':'key-up observed' if any(x['key_up'] for x in new) else 'no key-up observed; unmapped scans may lack key events'}
