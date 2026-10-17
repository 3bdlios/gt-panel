"""Exact-build HEVC DMA allocation fix. No module unload or automatic reboot."""
import hashlib,os,platform,tempfile
from pathlib import Path
ORIGINAL='c47fa7043757b2d8787f83e04c8db788ce30a75d5cee566d9f87b93123795379'
FIXED='829cd7d8fea5baedc302f6560e414bb4df75fea2b8d503c32123d0986cff11f4'
MODULE=Path('/lib/modules/5.15.196/extra/amvdec_h265.ko')
BACKUP=Path('/var/lib/gt-hevc/amvdec_h265.original.ko')
OFFSET=0x123d0

def digest(data):return hashlib.sha256(data).hexdigest()

def patched(data):
 if digest(data)!=ORIGINAL or data[OFFSET:OFFSET+4]!=bytes.fromhex('68020035'):raise RuntimeError('Unreviewed HEVC driver; no changes')
 result=data[:OFFSET]+bytes.fromhex('600200b5')+data[OFFSET+4:]
 if digest(result)!=FIXED:raise RuntimeError('Patched checksum mismatch')
 return result

def verify_host():
 if platform.release()!='5.15.196' or Path('/proc/device-tree/model').read_bytes().rstrip(b'\0\r\n ')!=b'GTMedia GT Combo':raise RuntimeError('Unsupported receiver/kernel; no changes')
 if MODULE.is_symlink() or BACKUP.is_symlink() or BACKUP.parent.is_symlink():raise RuntimeError('Unexpected symlink; no changes')

def atomic_write(path,data,mode):
 fd,name=tempfile.mkstemp(prefix='.gt-hevc-',dir=str(path.parent))
 try:
  with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.chmod(name,mode);os.replace(name,path)
  directory=os.open(str(path.parent),os.O_RDONLY)
  try:os.fsync(directory)
  finally:os.close(directory)
 finally:
  if os.path.exists(name):os.unlink(name)

def install():
 verify_host();data=MODULE.read_bytes()
 if digest(data)==FIXED:return 'HEVC fix already installed. Full reboot is required if not done yet.'
 result=patched(data)
 BACKUP.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 if BACKUP.exists():
  if digest(BACKUP.read_bytes())!=ORIGINAL:raise RuntimeError('Original backup mismatch; no changes')
 else:
  with BACKUP.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  BACKUP.chmod(0o600)
  directory=os.open(str(BACKUP.parent),os.O_RDONLY)
  try:os.fsync(directory)
  finally:os.close(directory)
 if BACKUP.read_bytes()!=data:raise RuntimeError('Backup verification failed; no changes')
 if MODULE.read_bytes()!=data:raise RuntimeError('Driver changed during installation; no changes')
 atomic_write(MODULE,result,MODULE.stat().st_mode & 0o777)
 if digest(MODULE.read_bytes())!=FIXED:raise RuntimeError('Driver readback mismatch')
 return 'HEVC fix installed. Restart the receiver fully to activate it; GUI restart is not enough.'

def restore():
 verify_host();data=MODULE.read_bytes()
 if digest(data)==ORIGINAL:return 'Original HEVC driver already present.'
 if digest(data)!=FIXED:raise RuntimeError('Unreviewed current driver; no changes')
 original=BACKUP.read_bytes()
 if digest(original)!=ORIGINAL:raise RuntimeError('Backup checksum mismatch; no changes')
 atomic_write(MODULE,original,MODULE.stat().st_mode & 0o777)
 if digest(MODULE.read_bytes())!=ORIGINAL:raise RuntimeError('Restore readback mismatch')
 return 'Original HEVC driver restored. Restart the receiver fully to activate it.'
