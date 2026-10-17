#!/usr/bin/env python3
"""GTCombo Android Fix — single-file installer

التعليمات:
هذا الملف يجمع إصلاح إعادة التشغيل إلى أندرويد وإصلاح اختيار أندرويد
من قائمة الإقلاع، لجهاز GTMedia GT Combo ذي محمّل الإقلاع المحدد فقط.
الطريقتان اختبرهما المستخدم؛ المثبت الموحد اختبر محلياً فقط.
ارفع هذا الملف إلى جذر مستودع 3bdlios/gt-panel، بجانب manifest.json.
الملف مستقل حالياً؛ رفعه وحده لا يضيف عنصراً قابلاً للتثبيت داخل GT Panel.

انسخ الملف إلى /tmp على الرسيفر، ثم افحص أولاً:
  python3 /tmp/GTCombo-Android-Fix.py --check
إذا ظهر CHECK OK، طبّق بعد مراجعة النتيجة:
  python3 /tmp/GTCombo-Android-Fix.py --apply
يحفظ نسخة رجوع ويطبع مسارها. لا يعيد التشغيل أو يكتب علم الإقلاع أثناء
التثبيت. يغيّر ملفات المساعد وقائمة الإقلاع على قسم USB فقط.
بعد نجاح التثبيت اختبر خيار أندرويد من قائمة الإقلاع ومن قائمة الطاقة.
يظل الفلاش موصولاً. الاختيار الصريح لأندرويد لاحقاً يكتب متغير التحويل
لمرة واحدة في قسم الإعدادات الداخلي، بعد حفظ نسخة والتحقق من CRC.
لا تفصل الكهرباء أثناء تلك العملية؛ الكتابة ليست ذرية عند فقد الطاقة.

الرجوع لملفات ما قبل التثبيت:
  python3 /tmp/GTCombo-Android-Fix.py --restore /etc/gtcombo-android-fix-backup-REPLACE
استبدل REPLACE بالمسار الذي طبعه المثبت. الاسترجاع يخص الملفات فقط ولا
يعيد كتابة إعدادات الإقلاع الداخلية. احتفظ بنسخة USB قابلة للاستعادة.
إذا ظهر STOP أو خطأ فلا تتجاوز الفحص أو تعد التشغيل قبل مراجعة السبب.

Default --check is read-only. --apply installs both menu fixes on USB root.
Later explicit Android selection arms the verified internal one-shot flag.
"""
from pathlib import Path
import argparse, hashlib, json, os, stat, subprocess, tempfile, types

PAYLOAD = {'/usr/lib/gtcombo/android-once.py': '#!/usr/bin/env python3\n"""Verified one-shot boot flag. Default --check is read-only. Never reboots."""\nimport argparse, hashlib, json, os, re, stat, struct, tempfile, zlib\nfrom pathlib import Path\nSIZE=65536\nBOOT_SHA=\'b6f01df81e74a83a52179b7cfdbaf5466833dae47c5b9a8202d9d66861ead36c\'\nBOOTCMD=b\'if test ${bootfromnand} = 1; then setenv bootfromnand 0; saveenv; else run bootfromsd; run bootfromusb; run bootfromemmc; fi; run storeboot\'\n\ndef sha(b): return hashlib.sha256(b).hexdigest()\n\ndef parse(raw):\n    if len(raw)!=SIZE or struct.unpack(\'<I\',raw[:4])[0] != zlib.crc32(raw[4:])&0xffffffff:\n        raise RuntimeError(\'Invalid 64KiB environment CRC\')\n    end=raw.find(b\'\\0\\0\',4)\n    if end<0: raise RuntimeError(\'No environment terminator\')\n    result={}\n    for entry in raw[4:end].split(b\'\\0\'):\n        if b\'=\' not in entry: raise RuntimeError(\'Invalid environment record\')\n        key,value=entry.split(b\'=\',1)\n        if key in result: raise RuntimeError(\'Duplicate environment key\')\n        result[key]=value\n    return result\n\ndef plan(raw):\n    env=parse(raw)\n    if env.get(b\'bootcmd\')!=BOOTCMD: raise RuntimeError(\'Boot command changed; stop for review\')\n    if env.get(b\'bootfromnand\')!=b\'0\': raise RuntimeError(\'One-shot flag is already set or unknown\')\n    needle=b\'\\0bootfromnand=0\\0\'\n    if raw.count(needle)!=1: raise RuntimeError(\'Ambiguous flag location\')\n    patched=bytearray(raw)\n    offset=raw.index(needle)+len(b\'\\0bootfromnand=\')\n    patched[offset]=ord(\'1\')\n    patched[:4]=struct.pack(\'<I\',zlib.crc32(patched[4:])&0xffffffff)\n    after=bytes(patched); expected=dict(env); expected[b\'bootfromnand\']=b\'1\'\n    if parse(after)!=expected: raise RuntimeError(\'Unexpected variable change\')\n    if any(raw[i]!=after[i] for i in range(4,SIZE) if i!=offset): raise RuntimeError(\'Unexpected byte change\')\n    return after,offset\n\ndef verify_host():\n    if Path(\'/proc/device-tree/model\').read_bytes().rstrip(b\'\\0\\r\\n \')!=b\'GTMedia GT Combo\':\n        raise RuntimeError(\'Unexpected hardware\')\n    for name,minor in ((\'/dev/bootloader\',1),(\'/dev/env\',4)):\n        s=os.stat(name)\n        if not stat.S_ISBLK(s.st_mode) or os.major(s.st_rdev)!=179 or os.minor(s.st_rdev)!=minor:\n            raise RuntimeError(\'Unexpected block device mapping: \'+name)\n    with open(\'/dev/bootloader\',\'rb\',buffering=0) as f:\n        if sha(f.read(4194304))!=BOOT_SHA: raise RuntimeError(\'Different bootloader\')\n    mounts=[l.split() for l in Path(\'/proc/mounts\').read_text().splitlines()]\n    root=next(m for m in mounts if m[1]==\'/\'); flash=next(m for m in mounts if m[1]==\'/flash\')\n    rdev=os.path.realpath(root[0]); fdev=os.path.realpath(flash[0])\n    if not re.fullmatch(r\'/dev/sd[a-z]+2\',rdev) or re.sub(r\'\\d+$\',\'\',rdev)!=re.sub(r\'\\d+$\',\'\',fdev):\n        raise RuntimeError(\'Backup directory must be on verified USB root\')\n    return rdev\n\ndef read_env():\n    with open(\'/dev/env\',\'rb\',buffering=0) as f: return f.read(SIZE)\n\ndef write_exact(fd,data):\n    off=0\n    while off<len(data):\n        n=os.pwrite(fd,data[off:],off)\n        if n<=0: raise RuntimeError(\'Short device write\')\n        off+=n\n    os.fsync(fd)\n\ndef main():\n    ap=argparse.ArgumentParser(description=__doc__)\n    ap.add_argument(\'--arm\',action=\'store_true\',help=\'Writes internal environment after verified backup\')\n    ap.add_argument(\'--expect-sha256\',help=\'Exact original environment hash from the read-only check\')\n    ap.add_argument(\'--check\',action=\'store_true\')\n    args=ap.parse_args()\n    if args.arm and args.check: raise RuntimeError(\'Select check or arm\')\n    root=verify_host(); before=read_env(); after,offset=plan(before)\n    print(\'BOOTLOADER MATCH; ENV CRC VALID; USB ROOT:\',root)\n    print(\'ENV_SHA256:\',sha(before))\n    print(\'NEW_ENV_SHA256:\',sha(after))\n    print(\'PLAN: bootfromnand 0 -> 1 at data byte\',offset,\'plus four CRC bytes; no other variables changed.\')\n    print(\'Existing bootcmd resets the flag to 0 before attempting internal Android.\')\n    if not args.arm:\n        print(\'CHECK ONLY: nothing written.\'); return\n    if os.geteuid()!=0 or args.expect_sha256!=sha(before):\n        raise RuntimeError(\'Root and matching --expect-sha256 required before writing\')\n    backup=Path(tempfile.mkdtemp(prefix=\'gtcombo-env-backup-\',dir=\'/etc\'))\n    os.chmod(backup,0o700)\n    for name,data in ((\'env-before.bin\',before),(\'env-armed.bin\',after)):\n        with (backup/name).open(\'xb\') as f: f.write(data); f.flush(); os.fsync(f.fileno())\n        if (backup/name).read_bytes()!=data: raise RuntimeError(\'Backup verification failed\')\n    meta={\'device\':\'/dev/env\',\'offset\':0,\'length\':SIZE,\'original_sha256\':sha(before),\'armed_sha256\':sha(after),\'bootloader_sha256\':BOOT_SHA}\n    with (backup/\'metadata.json\').open(\'x\') as f:\n        json.dump(meta,f,indent=2); f.flush(); os.fsync(f.fileno())\n    os.sync(); print(\'VERIFIED BACKUP:\',backup,flush=True)\n    fd=os.open(\'/dev/env\',os.O_RDWR|os.O_SYNC)\n    try:\n        if os.pread(fd,SIZE,0)!=before: raise RuntimeError(\'Environment changed after review; refusing write\')\n        try:\n            write_exact(fd,after)\n            if os.pread(fd,SIZE,0)!=after: raise RuntimeError(\'Armed environment readback mismatch\')\n        except Exception:\n            print(\'Write failed; attempting to restore verified original.\',flush=True)\n            write_exact(fd,before)\n            if os.pread(fd,SIZE,0)!=before: raise RuntimeError(\'CRITICAL: restore readback failed; do not reboot\')\n            raise\n    finally: os.close(fd)\n    print(\'ARMED AND READBACK VERIFIED. No reboot performed.\')\n    print(\'Keep this backup; do not arm again. Next normal reboot should bypass USB once.\')\n\nif __name__==\'__main__\':\n    try: main()\n    except Exception as e: print(\'STOP:\',e); raise SystemExit(1)\n', '/usr/lib/gtcombo/android-boot.py': '#!/usr/bin/env python3\n"""Shared one-shot Android helper; callers must obtain an explicit Android choice."""\nimport importlib.util, os, subprocess, sys\nfrom pathlib import Path\nTOOL=Path(\'/usr/lib/gtcombo/android-once.py\')\ndef main():\n    if len(sys.argv)!=2 or sys.argv[1] not in (\'--arm\',\'--check\'):\n        raise RuntimeError(\'Use --arm or --check; no automatic cancel/environment write\')\n    spec=importlib.util.spec_from_file_location(\'gt_android_once\',str(TOOL))\n    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n    m.verify_host(); raw=m.read_env(); m.plan(raw)\n    if sys.argv[1]==\'--check\':\n        print(\'ANDROID_HELPER_CHECK_OK: no changes\'); return\n    log=Path(\'/etc/gtcombo-android-last-request.log\')\n    if log.is_symlink():raise RuntimeError(\'Unexpected log symlink\')\n    with log.open(\'a\') as f:\n        f.write(\'ANDROID_REQUEST_SELECTED\\n\'); f.flush(); os.fsync(f.fileno())\n        result=subprocess.run([\'/usr/bin/python3\',str(TOOL),\'--arm\',\'--expect-sha256\',m.sha(raw)],stdout=f,stderr=subprocess.STDOUT)\n        f.write(\'RESULT=%d\\n\'%result.returncode); f.flush(); os.fsync(f.fileno())\n    if result.returncode:raise RuntimeError(\'Could not prepare Android. Log: \'+str(log))\n    print(\'ANDROID_ONCE_ARMED\',flush=True)\nif __name__==\'__main__\':\n    try:main()\n    except Exception as e:print(\'ANDROID_BOOT_ERROR:\',e,file=sys.stderr);sys.exit(1)\n', '/etc/init.d/gtcombo-boot-menu': '#!/bin/sh\n[ "$1" = stop ] && exit 0\n[ -e /run/gt-boot-menu-shown ] && exit 0\ntouch /run/gt-boot-menu-shown\n/usr/bin/python3 /usr/lib/gtcombo/boot-menu.py >>/tmp/gt-boot-menu.log 2>&1\nresult=$?\nif [ "$result" = 10 ]; then\n if /usr/bin/python3 /usr/lib/gtcombo/android-boot.py --arm >>/tmp/gt-boot-menu.log 2>&1; then\n  sync\n  /sbin/reboot -f\n fi\nfi\nexit 0\n'}
ALLOWED = {'/usr/lib/gtcombo/android-once.py': [None, '2c4a6cc1fb58ab23035b07296a56801370a41d0ee7b8d2404bf539fd2eeef8cb'], '/usr/lib/gtcombo/android-boot.py': ['1c09e5d5a586c83512709a7f844a4367e9d412169300e089a5bf9278ea4ec0a2', '67cf7fc3b17a8b8859cde3e086e9411c952c64c465dbab29ae66086fc1a3697e', '8e5467193b40b58b7b477bb293733fa67c80abf7ab0d9b1d5b3ef1560a1298a3'], '/etc/init.d/gtcombo-boot-menu': ['a873aec928f117b29d05d4fecdf1464467a7e64cec092810cb83d76b02b91165', '2700108bf51474aaf73e7e89a8d3c2fb5ffe1f4b25e38e512ad4dafb61cd0285']}
DIGESTS = {'/usr/lib/gtcombo/android-once.py': '2c4a6cc1fb58ab23035b07296a56801370a41d0ee7b8d2404bf539fd2eeef8cb', '/usr/lib/gtcombo/android-boot.py': '8e5467193b40b58b7b477bb293733fa67c80abf7ab0d9b1d5b3ef1560a1298a3', '/etc/init.d/gtcombo-boot-menu': 'a873aec928f117b29d05d4fecdf1464467a7e64cec092810cb83d76b02b91165'}


def sha(data):return hashlib.sha256(data).hexdigest()

def source(path):return PAYLOAD[path].encode('utf-8')

def verify_path(path):
    current=Path('/')
    for part in path.parts[1:]:
        current=current/part
        if current.is_symlink():raise RuntimeError('Symlink target refused: '+str(current))
    if path.exists() and not path.is_file():raise RuntimeError('Non-regular target: '+str(path))
    if not path.parent.is_dir():raise RuntimeError('Missing parent: '+str(path.parent))

def atomic(path,data,mode):
    fd,name=tempfile.mkstemp(prefix='.gt-android-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(name,mode);os.replace(name,path);os.sync()
        if path.read_bytes()!=data:raise RuntimeError('Readback mismatch: '+str(path))
    finally:
        if os.path.exists(name):os.unlink(name)

def module():
    m=types.ModuleType('gt_android_once_checked')
    exec(compile(source('/usr/lib/gtcombo/android-once.py'),'android-once.py','exec'),m.__dict__)
    return m

def snapshot(paths):
    result={}
    for p in paths:
        verify_path(p)
        result[p]=(p.read_bytes(),stat.S_IMODE(p.stat().st_mode)) if p.exists() else (None,0o755)
    return result

def restore_files(old):
    for p,(data,mode) in old.items():
        verify_path(p)
        if data is None:
            if p.exists():p.unlink()
        else:atomic(p,data,mode)
    os.sync()

def restore_backup(folder):
    root=folder.resolve()
    if folder.is_symlink() or root.parent!=Path('/etc') or not root.name.startswith('gtcombo-android-fix-backup-'):
        raise RuntimeError('Unexpected backup location')
    records=json.loads((root/'files.json').read_text())
    if not isinstance(records,list) or {r['path'] for r in records}!=set(PAYLOAD) or len(records)!=len(PAYLOAD):
        raise RuntimeError('Backup target inventory mismatch')
    restored={}
    for r in records:
        p=Path(r['path']);verify_path(p)
        if r['file'] is None:data=None
        else:
            if not isinstance(r['file'],str) or not r['file'].isdigit():raise RuntimeError('Invalid backup member')
            saved=root/r['file']
            if saved.is_symlink():raise RuntimeError('Backup symlink refused')
            data=saved.read_bytes()
            if sha(data)!=r['sha256']:raise RuntimeError('Backup hash mismatch')
        restored[p]=(data,r['mode'])
    current=snapshot(restored)
    try:restore_files(restored)
    except Exception:
        restore_files(current);raise
    print('RESTORED files and verified. Internal environment unchanged; no reboot.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--check',action='store_true')
    modes.add_argument('--apply',action='store_true')
    modes.add_argument('--restore',metavar='BACKUP_DIRECTORY')
    args=parser.parse_args()
    for name,text in PAYLOAD.items():
        if sha(text.encode())!=DIGESTS[name]:raise RuntimeError('Embedded payload checksum mismatch')
        if name.endswith('.py'):compile(text,name,'exec')
        else:subprocess.run(['/bin/sh','-n'],input=text.encode(),check=True)
    m=module();m.verify_host()
    if os.geteuid()!=0:raise RuntimeError('Run on receiver as root')
    if args.restore:
        restore_backup(Path(args.restore));return
    before=m.read_env();m.plan(before)
    targets=[Path(p) for p in PAYLOAD]
    old=snapshot(targets)
    for p,(data,mode) in old.items():
        digest=sha(data) if data is not None else None
        if digest not in ALLOWED[str(p)]:raise RuntimeError('Unreviewed existing file: '+str(p))
    print('CHECK OK: GTMedia GT Combo; matching bootloader; valid environment; flag=0.')
    print('Both menus will use the verified one-shot Android method.')
    print('Install changes USB-root files only. No boot flag write or reboot during installation.')
    if not args.apply:print('CHECK ONLY: nothing written.');return
    if all(old[p][0]==source(str(p)) for p in targets):
        print('ALREADY INSTALLED: no files changed.');return
    backup=Path(tempfile.mkdtemp(prefix='gtcombo-android-fix-backup-',dir='/etc'))
    records=[]
    for n,p in enumerate(targets):
        data,mode=old[p];name=str(n) if data is not None else None
        if data is not None:
            with (backup/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            if (backup/name).read_bytes()!=data:raise RuntimeError('Backup readback mismatch')
        records.append({'path':str(p),'file':name,'mode':mode,'sha256':sha(data) if data is not None else None})
    with (backup/'files.json').open('x') as f:json.dump(records,f,indent=2);f.flush();os.fsync(f.fileno())
    os.sync();print('VERIFIED BACKUP:',backup,flush=True)
    try:
        for p in targets:
            if (p.read_bytes() if p.exists() else None)!=old[p][0]:raise RuntimeError('Target changed since preflight')
        for p in targets:atomic(p,source(str(p)),old[p][1])
        if m.read_env()!=before:raise RuntimeError('Environment changed independently during install; do not reboot')
    except Exception:
        restore_files(old);raise
    print('INSTALLED AND READBACK VERIFIED: Android restart + startup selector.')
    print('No reboot performed. No environment write performed by installer.')
    print('On later explicit Android selection, the helper backs up and arms the internal one-shot flag.')

if __name__=='__main__':
    try:main()
    except Exception as e:print('STOP:',e);raise SystemExit(1)
