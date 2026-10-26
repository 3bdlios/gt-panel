#!/usr/bin/env python3
import pathlib, tempfile, shutil, subprocess, tarfile, io
ROOT=pathlib.Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'; DIST.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    stage=pathlib.Path(temp)/'stage'; plugin=stage/'usr/lib/enigma2/python/Plugins/Extensions/GTPanel'
    shutil.copytree(ROOT/'src/GTPanel',plugin,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    control=stage/'DEBIAN'; control.mkdir()
    text='Package: enigma2-plugin-extensions-gtpanel\nVersion: 2.2.0\nArchitecture: all\nMaintainer: GT Enigma2 Team\nSection: extra\nPriority: optional\nDepends: enigma2, python3-core, python3-twisted\nDescription: GT Panel safe GitHub catalog for GT Enigma2\n'
    (control/'control').write_text(text)
    (control/'postinst').write_text('#!/bin/sh\ncase "${1:-configure}" in configure|\'\') ( sleep 5; killall -TERM enigma2 2>/dev/null || true ) </dev/null >/dev/null 2>&1 & ;; esac\nexit 0\n'); (control/'postinst').chmod(0o755)
    subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(DIST/'enigma2-plugin-extensions-gtpanel_2.2.0_all.deb')],check=True)
    (control/'control').write_text(text.replace('Architecture: all','Architecture: all'))
    # opkg uses the conventional ar container with control and data tarballs.
    parts=pathlib.Path(temp)/'ipk'; parts.mkdir(); (parts/'debian-binary').write_bytes(b'2.0\n')
    def root_owner(info):
        info.uid=info.gid=0; info.uname=info.gname='root'; return info
    with tarfile.open(parts/'control.tar.gz','w:gz') as tf:
        for entry in control.iterdir(): tf.add(entry,arcname='./'+entry.name,filter=root_owner)
    with tarfile.open(parts/'data.tar.gz','w:gz') as tf: tf.add(stage/'usr',arcname='./usr',filter=root_owner)
    subprocess.run(['ar','r',str(DIST/'enigma2-plugin-extensions-gtpanel_2.2.0_all.ipk'),'debian-binary','control.tar.gz','data.tar.gz'],cwd=str(parts),check=True)
print(DIST)
