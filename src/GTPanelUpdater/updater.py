"""Pinned one-time GT Panel update after GUI startup."""
import hashlib,os,shutil,subprocess,tempfile,time
from pathlib import Path
from urllib.request import urlopen,Request
URL='https://raw.githubusercontent.com/3bdlios/gt-panel/main/dist/enigma2-plugin-extensions-gtpanel_2.2.1_all.ipk'
SHA256='b7e6cdf3a3a015c906c2b8b623a352ba41e458f725c4c38920c6b42039235455'
SIZE=29300

def install():
    if os.geteuid()!=0:raise RuntimeError('التحديث يتطلب صلاحيات النظام')
    opkg=shutil.which('opkg')
    if opkg not in ('/usr/bin/opkg','/bin/opkg','/usr/sbin/opkg','/sbin/opkg'):raise RuntimeError('مدير حزم الجهاز غير متاح')
    source=Path('/usr/lib/enigma2/python/Plugins/Extensions/GTPanel')
    if source.is_symlink() or not source.is_dir():raise RuntimeError('مسار البنل الحالي غير متوقع')
    if any(p.is_symlink() for p in source.rglob('*')):raise RuntimeError('البنل الحالي يحتوي روابط غير متوقعة')
    with urlopen(Request(URL,headers={'User-Agent':'GT-Panel-Updater/1.0'}),timeout=30) as response:
        data=response.read(SIZE+1)
    if len(data)!=SIZE or hashlib.sha256(data).hexdigest()!=SHA256:raise RuntimeError('ملف التحديث لا يطابق البصمة المعتمدة')
    root=_STATE
    if root.is_symlink():raise RuntimeError('مسار حالة التحديث غير متوقع')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    backup=Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S')+'-',dir=str(root)))
    shutil.copytree(source,backup/'GTPanel')
    package=backup/'gtpanel.ipk';package.write_bytes(data);package.chmod(0o600)
    try:
        with (backup/'install.log').open('wb') as log:
            os.chmod(str(backup/'install.log'),0o600)
            result=subprocess.run([opkg,'--force-reinstall','install',str(package)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=False)
        if result.returncode:raise RuntimeError('فشل التحديث. نسخة البنل السابقة وسجل الخطأ محفوظان في '+str(backup))
        mark_finished()
        return str(backup)
    finally:
        if package.exists():package.unlink()

_STATE=Path('/var/lib/gt-panel-updater')
_TAG='2.2.1-'+SHA256[:12]
def finished():
    return (_STATE/('done-'+_TAG)).is_file()

def claim_auto_attempt():
    if finished():return False
    if _STATE.is_symlink():raise RuntimeError('مسار حالة التحديث غير متوقع')
    _STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    try:fd=os.open(str(_STATE/('attempted-'+_TAG)),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:return False
    with os.fdopen(fd,'w') as f:f.write('One automatic attempt; manual retry is available.\n');f.flush();os.fsync(f.fileno())
    return True

def mark_finished():
    p=_STATE/('done-'+_TAG)
    with p.open('w') as f:f.write(SHA256+'\n');f.flush();os.fsync(f.fileno())
    p.chmod(0o600)
