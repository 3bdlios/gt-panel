#!/usr/bin/env python3
import pathlib, tarfile, io, hashlib, json
root=pathlib.Path(__file__).resolve().parents[1]/'repository'
items=[]
for category in ('Fixes','Plugins','Skins','Updates'):
    ident='demo-'+category.lower()
    path=('usr/share/enigma2/GT-Demo/README.txt' if category=='Skins' else 'usr/lib/enigma2/python/Plugins/Extensions/GTDemo/'+category+'.txt')
    content=('GT Panel '+category+' example. This is a harmless text file, not a device repair.\n').encode()
    bundle=root/(ident+'.tar.gz')
    with tarfile.open(bundle,'w:gz') as tf:
        info=tarfile.TarInfo(path); info.size=len(content); info.mode=0o644; tf.addfile(info,io.BytesIO(content))
    items.append({'id':ident,'title':'Demo '+category,'category':category,'version':'1.0.0','description':'Example only: installs a text file. No actual firmware repair/update.','url':'https://raw.githubusercontent.com/3bdlios/gt-panel/main/repository/'+bundle.name,'sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),'size':bundle.stat().st_size,'files':['/'+path],'compatibility':{'model':['REPLACE_WITH_ACTUAL_MODEL'],'image':['gt-enigma2'],'version':['REPLACE_WITH_IMAGE_REVISION'],'python':['REPLACE_WITH_PYTHON_MAJOR_MINOR']}})
(root/'manifest.json').write_text(json.dumps({'schema':1,'items':items},indent=2)+'\n')
