#!/usr/bin/env python3
"""Build the independent GT Remote package, with no installation scripts."""
import pathlib,tempfile,shutil,tarfile,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1];DIST=ROOT/'dist';DIST.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
 stage=pathlib.Path(temp)/'stage';dest=stage/'usr/lib/enigma2/python/Plugins/Extensions/GTRemote'
 shutil.copytree(ROOT/'src/GTRemote',dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 parts=pathlib.Path(temp)/'parts';parts.mkdir()
 (parts/'debian-binary').write_bytes(b'2.0\n')
 (parts/'control').write_text('Package: enigma2-plugin-extensions-gtremote\nVersion: 1.0.0\nArchitecture: all\nMaintainer: GT Enigma2 Team\nSection: extra\nPriority: optional\nDepends: enigma2, python3-core, enigma2-plugin-extensions-openwebif\nDescription: GT Remote standalone mobile OpenWebif remote on port 8088\n')
 def owner(info):info.uid=info.gid=0;info.uname=info.gname='root';return info
 with tarfile.open(parts/'control.tar.gz','w:gz') as tf:tf.add(parts/'control',arcname='./control',filter=owner)
 with tarfile.open(parts/'data.tar.gz','w:gz') as tf:
  for path in sorted(stage.rglob('*')):
   if path.is_file():tf.add(path,arcname='./'+str(path.relative_to(stage)),filter=owner)
 output=DIST/'enigma2-plugin-extensions-gtremote_1.0.0_all.ipk'
 if output.exists():output.unlink()
 subprocess.run(['ar','r',str(output),'debian-binary','control.tar.gz','data.tar.gz'],cwd=parts,check=True)
 print(output)
