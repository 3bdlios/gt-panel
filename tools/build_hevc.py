#!/usr/bin/env python3
"""Build HEVC repair tool; use --publish-catalog only after receiver acceptance."""
import argparse,gzip,hashlib,io,json,pathlib,sys,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from GTPanel import core
parser=argparse.ArgumentParser();parser.add_argument('--publish-catalog',action='store_true');args=parser.parse_args()
source=ROOT/'src/GTHEVC';output=ROOT/'repository/gtcombo-hevc-repair-1.0.1.tar.gz';raw=io.BytesIO();files=[]
with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as gz:
 with tarfile.open(fileobj=gz,mode='w') as tf:
  for name in ('__init__.py','repair.py','plugin.py'):
   data=(source/name).read_bytes();compile(data,name,'exec');path='usr/lib/enigma2/python/Plugins/Extensions/GTHEVC/'+name;files.append('/'+path)
   entry=tarfile.TarInfo(path);entry.size=len(data);entry.mode=0o644;tf.addfile(entry,io.BytesIO(data))
data=raw.getvalue();output.write_bytes(data)
if args.publish_catalog:
 item={'id':'gtcombo-hevc-repair','title':'H.265 channel restart repair','category':'Fixes','version':'1.0.1','description':'Repairs a confirmed HEVC NULL DMA allocation panic. Applies automatically after installation, keeps an original driver backup and restarts the receiver fully once. Restore is available from GT HEVC restart repair in the plugin menu.','warning':'The receiver automatically reboots once after successful application. No reboot on failure. Accepts only the tested GT Combo kernel 5.15.196 HEVC driver. Do not unload the decoder live.','compatibility':{'model':['GTMedia GT Combo'],'image':['openatv'],'version':['8.0.1.20261007'],'python':['3.14']},'url':'https://raw.githubusercontent.com/3bdlios/gt-panel/feature/ipk-one-click/repository/'+output.name,'format':'tar.gz','files':sorted(files),'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
 for path in (ROOT/'manifest-v2.json',ROOT/'repository/manifest-v2.json'):
  doc=json.loads(path.read_text());doc['items']=[i for i in doc['items'] if i['id']!=item['id']]+[item];core.validate(doc);path.write_text(json.dumps(doc,indent=2)+'\n')
print(output,hashlib.sha256(data).hexdigest())
