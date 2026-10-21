#!/usr/bin/env python3
"""Use only the unallocated tail of the known XCONN 4GiB USB image. Default: report only."""
import argparse,hashlib,json,os,re,shutil,stat,struct,subprocess,tempfile,uuid
from pathlib import Path
LAYOUT=[(8192,1048576,12),(1056768,6291456,131),(7348224,1040384,131)]
STATE=Path('/etc/xcenigma-recording-space')
MOUNT=Path('/media/hdd')

def sha(b):return hashlib.sha256(b).hexdigest()
def entries(raw):
 if len(raw)!=512 or raw[510:]!=b'\x55\xaa':raise RuntimeError('Invalid MBR')
 out=[]
 for i in range(4):
  row=raw[446+i*16:462+i*16];start,size=struct.unpack_from('<II',row,8)
  out.append({'start':start,'sectors':size,'type':row[4],'raw':row})
 return out

def plan(raw,sectors):
 e=entries(raw)
 for index,(start,size,kind) in enumerate(LAYOUT):
  if (e[index]['start'],e[index]['sectors'],e[index]['type'])!=(start,size,kind):raise RuntimeError('Different image partition layout; refusing changes')
 if sectors>0xffffffff:raise RuntimeError('Disk exceeds supported MBR capacity')
 if sectors<=8388608+2097152:raise RuntimeError('Less than 1GiB of extra space available')
 start=8388608;size=((sectors-start)//2048)*2048
 if e[3]['raw']!=bytes(16):raise RuntimeError('Partition 4 already exists; no automatic reuse or format')
 entry=struct.pack('<B3sB3sII',0,b'\xfe\xff\xff',131,b'\xfe\xff\xff',start,size)
 after=raw[:494]+entry+raw[510:]
 assert after[:494]==raw[:494] and after[510:]==raw[510:]
 return after,start,size

def mounts():
 return [line.split() for line in Path('/proc/mounts').read_text().splitlines()]
def physical():
 if Path('/proc/device-tree/model').read_bytes().rstrip(b'\0\r\n ')!=b'XCONN':raise RuntimeError('This script is for the XCONN image only')
 m=mounts();root=next(x for x in m if x[1]=='/');flash=next(x for x in m if x[1]=='/flash');storage=next(x for x in m if x[1]=='/storage')
 dev=os.path.realpath(root[0]);match=re.fullmatch(r'/dev/(sd[a-z]+)2',dev)
 if not match:raise RuntimeError('Root must be partition 2 of a USB disk; internal eMMC is never accepted')
 disk='/dev/'+match[1]
 if os.path.realpath(flash[0])!=disk+'1' or os.path.realpath(storage[0])!=disk+'3':raise RuntimeError('Root, flash and storage must share the same USB disk')
 for path in (disk,disk+'1',disk+'2',disk+'3'):
  if not stat.S_ISBLK(os.stat(path).st_mode):raise RuntimeError('Expected block device')
 sysdisk=Path('/sys/class/block')/match[1]
 if int((sysdisk/'queue/logical_block_size').read_text())!=512:raise RuntimeError('Only 512-byte sectors are supported')
 sectors=int((sysdisk/'size').read_text())
 with open(disk,'rb',buffering=0) as f:raw=f.read(512)
 # Never overwrite GPT metadata, even if a hybrid MBR resembles the image.
 with open(disk,'rb',buffering=0) as f:
  f.seek(512);front=f.read(8);f.seek((sectors-1)*512);tail=f.read(8)
 if front==b'EFI PART' or tail==b'EFI PART':raise RuntimeError('GPT metadata found; refusing changes')
 return disk,sectors,raw

def atomic_json(path,value):
 fd,tmp=tempfile.mkstemp(prefix='.state-',dir=str(path.parent))
 try:
  with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path);os.sync()
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def mounted_device(device):
 resolved=os.path.realpath(device)
 return any(os.path.realpath(m[0])==resolved for m in mounts() if m[0].startswith('/dev/'))
def uuid_of(device):
 p=subprocess.run(['blkid','-s','UUID','-o','value',device],capture_output=True,text=True)
 if p.returncode not in (0,2):raise RuntimeError('Cannot inspect target filesystem')
 return p.stdout.strip()
def verify_node(device,state):
 p=Path('/sys/class/block')/Path(device).name
 if not p.exists() or not Path(device).exists():return False
 if not stat.S_ISBLK(os.stat(device).st_mode):raise RuntimeError('Target is not a block device')
 if int((p/'start').read_text())!=state['start'] or int((p/'size').read_text())!=state['sectors']:raise RuntimeError('Kernel partition mapping differs; reboot before proceeding')
 return True

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true',help='Create partition, then after a reboot format and mount it');args=ap.parse_args()
 if os.geteuid()!=0:raise RuntimeError('Run as root')
 disk,total,raw=physical();e=entries(raw)
 print('USB disk:',disk,'Capacity GiB:',round(total*512/2**30,2))
 print('System partitions 1-3 will remain unchanged.')
 for i,p in enumerate(e,1):print('Partition',i,'start',p['start'],'sectors',p['sectors'],'type',p['type'])
 statepath=STATE/'pending.json';state=None
 if statepath.exists():
  if statepath.is_symlink():raise RuntimeError('Unexpected state symlink')
  state=json.loads(statepath.read_text())
  if state['disk']!=disk or state['disk_sectors']!=total or state['mbr_after_sha256']!=sha(raw):raise RuntimeError('Disk changed since preparation; refusing format')
  for i,(start,size,kind) in enumerate(LAYOUT):
   if (e[i]['start'],e[i]['sectors'],e[i]['type'])!=(start,size,kind):raise RuntimeError('Protected partition changed')
  if (e[3]['start'],e[3]['sectors'],e[3]['type'])!=(state['start'],state['sectors'],131):raise RuntimeError('Unexpected partition 4')
  print('Known prepared partition:',disk+'4','GiB:',round(state['sectors']*512/2**30,2))
 else:
  after,start,size=plan(raw,total)
  print('Unallocated space to use GiB:',round(size*512/2**30,2))
 if not args.apply:
  print('CHECK ONLY. Nothing changed. Use --apply to prepare the unused space.');return
 for tool in ('mkfs.ext4','blkid','mount'):
  if not shutil.which(tool):raise RuntimeError('Required tool missing: '+tool+'; no automatic package install')
 # Never replace another disk or a populated directory at /media/hdd.
 if MOUNT.is_symlink():raise RuntimeError('/media/hdd is a symlink; configure an explicit mountpoint first')
 for m in mounts():
  if m[1]==str(MOUNT) or m[1].startswith(str(MOUNT)+'/'):
   if not state or os.path.realpath(m[0])!=disk+'4':raise RuntimeError('/media/hdd is already used by another filesystem')
 if MOUNT.exists() and not os.path.ismount(MOUNT) and any(MOUNT.iterdir()):raise RuntimeError('/media/hdd contains files; refusing to hide them')
 fstab=Path('/etc/fstab');fstext=fstab.read_text() if fstab.exists() else ''
 for line in fstext.splitlines():
  columns=line.split()
  if line.lstrip().startswith('#') or len(columns)<2:continue
  if columns[1]==str(MOUNT) and (not state or columns[0]!='UUID='+state['uuid']):raise RuntimeError('Existing /media/hdd entry in fstab; refusing to replace it')
 if state is None:
  if STATE.is_symlink():raise RuntimeError('Unexpected state directory symlink')
  STATE.mkdir(mode=0o700,exist_ok=True)
  backup=STATE/'mbr-before.bin'
  if backup.exists():raise RuntimeError('An earlier MBR backup exists without matching state; inspect it first')
  with backup.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  backup.chmod(0o600)
  state={'disk':disk,'disk_sectors':total,'start':start,'sectors':size,'uuid':str(uuid.uuid4()),'mbr_before_sha256':sha(raw),'mbr_after_sha256':sha(after),'phase':'partition_created'}
  # Persist recovery metadata before the disk write.
  atomic_json(statepath,state)
  fd=os.open(disk,os.O_RDWR|os.O_SYNC)
  try:
   if os.pread(fd,512,0)!=raw:raise RuntimeError('MBR changed during preparation')
   try:
    if os.pwrite(fd,after[494:510],494)!=16:raise RuntimeError('Short partition entry write')
    os.fsync(fd)
    if os.pread(fd,512,0)!=after:raise RuntimeError('Partition write readback failed')
   except Exception:
    os.pwrite(fd,raw[494:510],494);os.fsync(fd)
    if os.pread(fd,512,0)!=raw:raise RuntimeError('CRITICAL: MBR restore failed; do not reboot')
    raise
  finally:os.close(fd)
  print('PARTITION CREATED. Backup:',backup)
  print('Reboot Enigma2 DEVICE, then run this script with --apply again. No formatting performed yet.');return
 device=disk+'4'
 if not verify_node(device,state):raise RuntimeError('New partition not visible. Reboot the device, then run --apply again')
 known_uuid=uuid_of(device)
 if known_uuid and known_uuid!=state['uuid']:raise RuntimeError('Target contains an unexpected filesystem; refusing to erase it')
 if not known_uuid:
  if state.get('phase') in ('formatted','ready'):raise RuntimeError('Previously prepared filesystem is now missing; refusing to reformat')
  if mounted_device(device):raise RuntimeError('Target is mounted; refusing to format')
  subprocess.run(['mkfs.ext4','-q','-m','0','-L','RECORDINGS','-U',state['uuid'],device],stdin=subprocess.DEVNULL,check=True)
  if uuid_of(device)!=state['uuid']:raise RuntimeError('New filesystem UUID verification failed')
  state['phase']='formatted';atomic_json(statepath,state)
 if not os.path.ismount(MOUNT):
  if mounted_device(device):raise RuntimeError('Target was automounted elsewhere; unmount it first, without formatting again')
  MOUNT.mkdir(parents=True,exist_ok=True)
  subprocess.run(['mount','-t','ext4','-o','noatime',device,str(MOUNT)],check=True)
 for name in ('movie','timeshift'):(MOUNT/name).mkdir(exist_ok=True)
 line='UUID='+state['uuid']+' '+str(MOUNT)+' ext4 defaults,noatime 0 2'
 if not any(l.split()[:2]==['UUID='+state['uuid'],str(MOUNT)] for l in fstext.splitlines() if not l.lstrip().startswith('#')):
  if fstab.is_symlink():raise RuntimeError('fstab is a symlink; mount is temporary, no persistent change made')
  fb=STATE/'fstab-before'
  if not fb.exists():fb.write_text(fstext);fb.chmod(0o600)
  with fstab.open('a') as f:f.write(('' if not fstext or fstext.endswith('\n') else '\n')+line+'\n');f.flush();os.fsync(f.fileno())
 state['phase']='ready';atomic_json(statepath,state);os.sync()
 print('READY. Recording directory: /media/hdd/movie/ ; Timeshift directory: /media/hdd/timeshift/')
 print('Select these paths in Enigma2 recording/timeshift settings. Automatic timeshift was not enabled.')
 print('Free GiB:',round(shutil.disk_usage(MOUNT).free/2**30,2))
if __name__=='__main__':
 try:main()
 except Exception as e:print('STOP:',e,file=__import__('sys').stderr);raise SystemExit(1)
