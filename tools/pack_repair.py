#!/usr/bin/env python3
"""Pack a declarative repair from a JSON spec and a payload directory.
Usage: pack_repair.py SPEC.json PAYLOAD_DIRECTORY OUTPUT.tar.gz
The spec has id/category/title/version/description/compatibility/targets/checks.
Targets map absolute receiver paths to sha256, before (hashes or null), mode.
Files are read from PAYLOAD_DIRECTORY + target.lstrip('/'). No script execution.
"""
import pathlib, sys, json, hashlib, tarfile, io
spec=pathlib.Path(sys.argv[1]); root=pathlib.Path(sys.argv[2]).resolve(); out=pathlib.Path(sys.argv[3])
item=json.loads(spec.read_text()); item.update(action='repair',min_engine=2,files=sorted(item['targets']))
with tarfile.open(out,'w:gz') as tf:
    for path in item['files']:
        p=(root/path.lstrip('/')).resolve()
        if root not in p.parents:raise SystemExit('Payload path escapes source root')
        data=p.read_bytes(); actual=hashlib.sha256(data).hexdigest()
        if item['targets'][path]['sha256']!=actual:raise SystemExit('Per-file digest mismatch: '+path)
        info=tarfile.TarInfo(path.lstrip('/'));info.size=len(data);info.mode=item['targets'][path]['mode'];info.mtime=0
        tf.addfile(info,io.BytesIO(data))
item['sha256']=hashlib.sha256(out.read_bytes()).hexdigest();item['size']=out.stat().st_size
out.with_suffix(out.suffix+'.item.json').write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n')
print(out)
