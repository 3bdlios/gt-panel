#!/usr/bin/env python3
"""Add Remote read-only IR diagnostic. No uploads, keymap or driver changes."""
import datetime
import glob
import gzip
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

EVENT = struct.Struct('@llHHi')

def read(path, limit=65536):
    try:
        return Path(path).read_text(errors='replace')[:limit]
    except OSError as e:
        return 'UNAVAILABLE: ' + str(e)

def command(args):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=8)
        return {'status': p.returncode, 'output': p.stdout[:32768]}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {'error': str(e)}

def decode(data):
    if len(data) % EVENT.size:
        raise ValueError('Partial input_event record')
    return [{'device_seconds': sec, 'microseconds': usec, 'type': typ,
             'code': code, 'value': value,
             'scan_hex': '%08x' % (value & 0xffffffff) if typ == 4 and code == 4 else None}
            for sec, usec, typ, code, value in EVENT.iter_unpack(data)]

def metadata():
    result = {'tool_version': '1.0', 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'kernel': os.uname().release, 'architecture': os.uname().machine,
              'python': sys.version, 'input_event_bytes': EVENT.size,
              'image': read('/etc/image-version'), 'runlevel': command(['runlevel']),
              'modules': read('/proc/modules'), 'devices': [], 'rc': [],
              'lirc_nodes': glob.glob('/dev/lirc[0-9]*'),
              'enigma_inittab': [s for s in read('/etc/inittab').splitlines() if s.startswith('gui:')]}
    for path in sorted(glob.glob('/sys/class/input/event[0-9]*')):
        p = Path(path)
        result['devices'].append({'node': '/dev/input/'+p.name, 'sysfs': os.path.realpath(path),
            **{name: read(str(p/'device'/name),4096).strip() for name in
               ('name','phys','id/bustype','id/vendor','id/product','capabilities/ev','capabilities/msc','capabilities/key')}})
    for path in sorted(glob.glob('/sys/class/rc/rc[0-9]*')):
        result['rc'].append({'sysfs': os.path.realpath(path), 'protocols': read(path+'/protocols',4096),
                             'uevent': read(path+'/uevent',4096)})
    for path in ('/proc/stb/info/model','/proc/stb/info/boxtype','/proc/stb/info/chipset',
                 '/proc/stb/ir/rc/type','/proc/stb/ir/rc/mask0','/proc/stb/ir/rc/mask1',
                 '/proc/stb/ir/rc/customcode'):
        if os.path.isfile(path): result[path] = read(path,4096)
    try:
        with gzip.open('/proc/config.gz','rt') as f:
            result['kernel_ir_config'] = [s.strip() for s in f if any(x in s for x in
                ('CONFIG_RC_', 'CONFIG_IR_', 'CONFIG_LIRC', 'CONFIG_INPUT_EVDEV'))]
    except OSError:
        result['kernel_ir_config'] = 'Not exposed by running kernel'
    return result
