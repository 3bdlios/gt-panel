#!/usr/bin/env python3
"""Reproducible, declarative GT Panel repair bundle; no installer scripts."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from GTPanel import core

source = ROOT/'src/GTWiFi24'
dest = ROOT/'repository/gtcombo-wifi24-1.0.1.tar.gz'
prefix = '/usr/lib/enigma2/python/Plugins/Extensions/GTWiFi24/'
targets = {}
previous = next((i for i in json.loads((ROOT/'manifest-v2.json').read_text())['items'] if i['id']=='gtcombo-wifi24'), {})
raw = io.BytesIO()
with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as gz:
    with tarfile.open(fileobj=gz, mode='w') as tf:
        for name in ('__init__.py', 'plugin.py', 'repair.py'):
            data = (source/name).read_bytes()
            compile(data, name, 'exec')
            path = prefix+name
            targets[path] = {'before': [None], 'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o644}
            old = previous.get('targets', {}).get(path, {})
            for digest in old.get('before', []) + [old.get('sha256')]:
                if digest not in targets[path]['before']:
                    targets[path]['before'].append(digest)
            entry = tarfile.TarInfo(path.lstrip('/'))
            entry.size = len(data)
            entry.mode = 0o644
            entry.mtime = 0
            tf.addfile(entry, io.BytesIO(data))
bundle = raw.getvalue()
dest.write_bytes(bundle)
doc = json.loads((ROOT/'manifest-v2.json').read_text())
item = {
    'id': 'gtcombo-wifi24', 'title': 'Wi-Fi stability: 2.4 GHz mode',
    'category': 'Fixes', 'version': '1.0.1', 'action': 'repair', 'min_engine': 2,
    'description': 'Workaround for GT Combo Wi-Fi hangs: limits saved wlan0 networks to 2.4 GHz. Requires manual GUI restart after installation. Restore previous band settings from the GT Wi-Fi plugin menu.',
    'warning': 'May reconnect Wi-Fi once on first GUI start. 5-GHz-only networks cannot connect in this mode. Does not fix the kernel/SDIO driver. Ethernet and passwords are preserved; no automatic reboot.',
    'compatibility': doc['items'][0]['compatibility'],
    'url': 'https://raw.githubusercontent.com/3bdlios/gt-panel/feature/ipk-one-click/repository/'+dest.name,
    'format': 'tar.gz', 'files': sorted(targets), 'targets': targets,
    'sha256': hashlib.sha256(bundle).hexdigest(), 'size': len(bundle),
}
doc['items'] = [i for i in doc['items'] if i['id'] != item['id']] + [item]
core.validate(doc)
for path in (ROOT/'manifest-v2.json', ROOT/'repository/manifest-v2.json'):
    existing = json.loads(path.read_text())
    existing['items'] = [i for i in existing['items'] if i['id'] != item['id']] + [item]
    core.validate(existing)
    path.write_text(json.dumps(existing, indent=2)+'\n')
print('Validated bundle:', dest.name, 'bytes:',len(bundle),'sha256:',item['sha256'])
