#!/usr/bin/python3
"""Amlogic hardware adapter; all service parameters come from Enigma DVB ioctls."""
import os,fcntl,struct,time,signal,subprocess,sys,re
from pathlib import Path
vpid,apid,pcr,vtype,parent=map(int,sys.argv[1:6]);acodec=sys.argv[6]
if vtype not in (0,1,7):raise SystemExit('Unsupported video codec')
if not 0<vpid<8191:raise SystemExit('Invalid video PID')
def read(p):return Path(p).read_text().strip()
def write(p,v):Path(p).write_text(str(v))
def restore_saved_aspect():
 # Enigma2 stores the 4:3 policy, but decoder/boot defaults may overwrite it.
 # Restore only an explicitly saved supported value, after video setup.
 try:
  values={}
  for line in Path('/etc/enigma2/settings').read_text().splitlines():
   if '=' in line:
    key,value=line.split('=',1);values[key]=value.strip()
  policy=values.get('config.av.policy_43')
  if policy not in {'2','6','7','8','9'}:return
  target=Path('/sys/class/video/screen_mode')
  if target.read_text().split(':',1)[0].strip()!=policy:
   target.write_text(policy)
   print('RESTORED SAVED ASPECT',policy,flush=True)
 except (OSError,ValueError) as error:
  print('Saved aspect restore skipped',str(error),flush=True)
def stop(*_):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
fds=[];audio=None;oldroute=None;saved={};ca_active=False
try:
 lock=open('/run/gt-native-hardware.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for p in ('/sys/class/stb/source','/sys/class/stb/demux0_source','/sys/class/stb/demux1_source'):
  saved[p]=read(p)
 av=os.open('/dev/amvideo',os.O_RDWR);fds.append(av)
 route_map=read('/sys/class/vfm/map');match=re.search(r'\bdefault \{([^}]+)\}',route_map)
 if not match:raise RuntimeError('No default video route')
 oldroute=re.sub(r'\(\d+\)','',match.group(1)).strip();route='decoder amvideo' if vtype==7 else 'decoder deinterlace amvideo'
 if oldroute!=route:write('/sys/class/vfm/map','rm default');write('/sys/class/vfm/map','add default '+route)
 decoder=os.open('/dev/amstream_mpts_sched' if vtype==7 else '/dev/amstream_mpts',os.O_WRONLY|os.O_NONBLOCK);fds.append(decoder)
 for cmd,val in ((0x04,{0:0,1:2,7:11}[vtype]),(0x06,vpid),(0x4f,pcr),(0x90,0)):
  fcntl.ioctl(decoder,0x40045300|cmd,val)
 info={0:(0,720,576,3840,0,0,0,0,0),1:(4,1280,720,1920,0,0,0,0,0),7:(0,3840,2160,3840,0,0,0,0,0)}[vtype]
 fcntl.ioctl(decoder,0x4004530a,struct.pack('7I4xQQ',*info));fcntl.ioctl(decoder,0x5311,0)
 for p in saved:write(p,'ts1')
 # Reuse the descrambler currently allocated by the CAM for native video.
 # CA1 can hold valid keys while its hardware route is still bypassed.
 for index in (0,1):
  free=Path('/sys/class/stb/dsc%d_free_dscs'%index)
  route='/sys/class/stb/dsc%d_source'%index
  if free.exists() and int(free.read_text())<8:
   saved[route]=read(route)
   if saved[route]!='dmx0-dmx0':write(route,'dmx0')
   print('NATIVE CA ROUTE',index,read(route),flush=True)
   ca_active=True
 if ca_active:
  saved['/sys/class/stb/dvr0_mode']=read('/sys/class/stb/dvr0_mode')
  write('/sys/class/stb/dvr0_mode','pid')
  # Decrypted DMX0 feeds both video and native audio. Keep FIFO0 for network DMX2.
  for path,value in (('/sys/class/stb/asyncfifo0_source','dmx2'),('/sys/class/stb/asyncfifo1_source','dmx0')):
   saved[path]=read(path);write(path,value)
 write('/sys/class/tsync/enable',1)
 for cmd,ptr,val in ((0x40045327,True,0),(0x40045388,False,1),(0x40045317,False,0),(0x40045322,False,1),(0x40045349,True,0)):
  fcntl.ioctl(av,cmd,struct.pack('I',val) if ptr else val)
 write('/sys/class/amhdmitx/amhdmitx0/config','sdr')
 deadline=time.monotonic()+6
 while time.monotonic()<deadline:
  pts=int(read('/sys/class/tsync/pts_video'),16)
  if pts and pts!=0xffffffff:break
  time.sleep(.05)
 else:raise RuntimeError('Decoder produced no video PTS')
 write('/sys/class/tsync/pts_pcrscr',hex(pts));fcntl.ioctl(av,0x40045388,0)
 restore_saved_aspect()
 if 0<apid<8191 and acodec!='none':
  audio_env=os.environ.copy()
  audio_env['LD_PRELOAD']='/usr/lib/gtcombo/libgt-ts-tee.so'
  audio=subprocess.Popen(['/usr/lib/gtcombo/gt-native-audio-ca' if ca_active else '/usr/lib/gtcombo/gt-native-audio',str(apid),'0',acodec],close_fds=True,env=audio_env)
 else:write('/sys/class/tsync/enable',0)
 print('NATIVE VIDEO READY',vpid,apid,pcr,vtype,acodec,hex(pts),flush=True)
 while True:
  os.kill(parent,0)
  if audio and audio.poll() is not None:raise RuntimeError('Native audio adapter exited '+str(audio.returncode))
  time.sleep(.25)
except KeyboardInterrupt:pass
finally:
 signal.signal(signal.SIGTERM,signal.SIG_IGN);signal.signal(signal.SIGINT,signal.SIG_IGN)
 if audio and audio.poll() is None:
  audio.terminate()
  try:audio.wait(timeout=3)
  except subprocess.TimeoutExpired:audio.kill();audio.wait(timeout=2)
 for fd in reversed(fds):os.close(fd)
 if oldroute:
  write('/sys/class/vfm/map','rm default');write('/sys/class/vfm/map','add default '+oldroute)
 for p,v in saved.items():write(p,v)
 write('/sys/class/stb/demux0_source','ts1');write('/sys/class/stb/demux1_source','ts1')
 write('/sys/class/amhdmitx/amhdmitx0/config','sdr')
 print('NATIVE HARDWARE RELEASED',flush=True)
