#!/usr/bin/env python3
"""Repackage the reviewed clock repair and accept a docstring-only local variant."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from GTPanel import core, ipk

old = ROOT/'repository/gtcombo-frontpanel-fix_1.0.0_all.ipk'
members = {}
blob = old.read_bytes()
assert blob[:8] == b'!<arch>\n'
pos = 8
while pos < len(blob):
    header = blob[pos:pos+60]
    name = header[:16].decode().strip().rstrip('/')
    size = int(header[48:58])
    members[name] = blob[pos+60:pos+60+size]
    pos += 60+size+(size % 2)

with tempfile.TemporaryDirectory() as temp:
    stage = Path(temp)
    (stage/'debian-binary').write_bytes(b'2.0\n')
    data_name = next(n for n in members if n.startswith('data.tar'))
    (stage/data_name).write_bytes(members[data_name])
    with tarfile.open(fileobj=io.BytesIO(members['control.tar.gz'])) as tf:
        control_member = next(m for m in tf if m.name.lstrip('./') == 'control')
        control = tf.extractfile(control_member).read().decode()
    control = re.sub(r'(?m)^Version:.*$', 'Version: 1.0.1', control)
    with tarfile.open(stage/'control.tar.gz','w:gz') as tf:
        entry = tarfile.TarInfo('./control')
        raw = control.encode()
        entry.size = len(raw)
        entry.mode = 0o644
        tf.addfile(entry,io.BytesIO(raw))
    dest = ROOT/'repository/gtcombo-frontpanel-fix_1.0.1_all.ipk'
    subprocess.run(['ar','rc',str(dest),'debian-binary','control.tar.gz',data_name],cwd=stage,check=True)

path = '/usr/lib/enigma2/python/Plugins/Extensions/GTFrontPanel/plugin.py'
reviewed = '4e9ee5624eb10a76e6ed50d27d51447bd379e5b59e19b81ee4d7ab9f27accf13'
for target in (ROOT/'manifest-v2.json',ROOT/'repository/manifest-v2.json'):
    doc = json.loads(target.read_text())
    item = next((i for i in doc['items'] if i['id']=='gtcombo-frontpanel'), None)
    if item is None:
        continue
    if reviewed not in item['targets'][path]['before']:
        item['targets'][path]['before'].append(reviewed)
    item['version'] = '1.0.1'
    item['url'] = item['url'].replace('_1.0.0_all.ipk','_1.0.1_all.ipk')
    item['size'] = dest.stat().st_size
    item['sha256'] = hashlib.sha256(dest.read_bytes()).hexdigest()
    item['warning'] = 'Controls GPIOAO_2/3 in a separate process. Requires manual GUI restart. Reviewed local docstring variant accepted; hardware driver unchanged.'
    core.validate(doc)
    payload = ipk.payload(dest.read_bytes(),set(item['files']))
    for file,data in payload.items():
        assert hashlib.sha256(data).hexdigest()==item['targets'][file]['sha256']
    published = payload[path].decode()
    local = published.replace('GT Combo permanent local clock.', 'GT Combo channel number / standby clock.')
    assert hashlib.sha256(local.encode()).hexdigest()==reviewed
    assert compile(published,path,'exec').co_code == compile(local,path,'exec').co_code
    target.write_text(json.dumps(doc,indent=2)+'\n')
print('Front-panel 1.0.1: reviewed variant differs only in module docstring; payload unchanged and all digests verified.')
