#!/usr/bin/env python3
"""Bounded GT Combo DVB-T/T2 diagnostics. No tuning, route writes or repair."""
import os,sys,json,time,re,struct,ctypes,fcntl,select,subprocess,tempfile,signal,hashlib,urllib.request,xml.etree.ElementTree as ET,argparse
from pathlib import Path
VERSION='1.0.0'
PROBE_STOPPED=False
SYSTEMS={3:'DVB-T',16:'DVB-T2',1:'DVB-C-A',2:'DVB-C-B',5:'DVB-S',6:'DVB-S2',18:'DVB-C-C'}
def read(p,limit=262144):
 try:
  with open(p,'rb') as f:return f.read(limit).decode('utf-8','replace')
 except OSError:return ''
def clean(s):
 s=re.sub(r'https?://[^\s<>"\x27]+','[URL]',str(s))
 s=re.sub(r'(?im)^.*(?:password|passwd|psk|ssid|username|authorization|secret|token)\s*[:=].*$','[PRIVATE LINE]',s)
 s=re.sub(r'\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b','[MAC]',s)
 s=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[IPv4]',s)
 return s
class CallError(Exception):pass
def prop(fd,cmd):
 p=ctypes.create_string_buffer(76);struct.pack_into('I',p,0,cmd)
 args=struct.pack('I4xQ',1,ctypes.addressof(p));fcntl.ioctl(fd,0x80106f53,args)
 result=struct.unpack_from('i',p,72)[0]
 if result<0:raise CallError('DTV result '+str(result))
 return p.raw
def frontend(path):
 if ctypes.sizeof(ctypes.c_void_p)!=8:return {'error':'Only the reviewed 64-bit DVB ABI is probed'}
 fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK);out={'node':path}
 try:
  b=bytearray(168);fcntl.ioctl(fd,0x80a86f3d,b);out.update(name=b[:128].split(b'\0')[0].decode(errors='replace'),legacy_type=struct.unpack_from('I',b,128)[0],capabilities_hex=hex(struct.unpack_from('I',b,164)[0]))
  for name,cmd in [('systems',44),('frequency_hz',3),('bandwidth_hz',5),('delivery_system',17),('stream_id',42),('modulation',4),('guard_interval',38),('transmission_mode',39),('hierarchy',40),('fec_hp',36),('fec_lp',37)]:
   try:
    raw=prop(fd,cmd)
    out[name]=list(raw[16:16+min(32,struct.unpack_from('I',raw,48)[0])]) if cmd==44 else struct.unpack_from('I',raw,16)[0]
   except (OSError,CallError) as e:out[name]={'error':type(e).__name__,'detail':str(e)[:120]}
  out['statistics']={}
  for name,cmd in [('signal',62),('cnr',63),('pre_error_bits',64),('pre_total_bits',65),('post_error_bits',66),('post_total_bits',67),('error_blocks',68),('total_blocks',69)]:
   try:
    b=prop(fd,cmd);values=[]
    for i in range(min(b[16],4)):
     off=17+9*i;scale=b[off];value=struct.unpack_from('q' if scale==1 else 'Q',b,off+1)[0]
     values.append({'scale':{0:'unavailable',1:'dB_milli',2:'relative_0_65535',3:'counter'}.get(scale,str(scale)),'value':value})
    out['statistics'][name]=values
   except (OSError,CallError) as e:out['statistics'][name]={'error':type(e).__name__}
  status=bytearray(4);fcntl.ioctl(fd,0x80046f45,status);st=struct.unpack('I',status)[0]
  out['status']={'raw':st,'flags':[name for bit,name in [(1,'SIGNAL'),(2,'CARRIER'),(4,'VITERBI'),(8,'SYNC'),(16,'LOCK'),(32,'TIMEDOUT'),(64,'REINIT')] if st&bit]}
  for name,request,size in [('legacy_signal',0x80026f47,2),('legacy_snr',0x80026f48,2),('legacy_ber',0x80046f46,4),('uncorrected_blocks',0x80046f49,4)]:
   try:b=bytearray(size);fcntl.ioctl(fd,request,b);out[name]=int.from_bytes(b,sys.byteorder)
   except OSError as e:out[name]={'errno':e.errno}
  out['delivery_name']=SYSTEMS.get(out.get('delivery_system'),str(out.get('delivery_system')))
  return out
 finally:os.close(fd)
def crc32_mpeg(data):
 c=0xffffffff
 for x in data:
  c^=x<<24
  for _ in range(8):c=((c<<1)^0x04c11db7)&0xffffffff if c&0x80000000 else (c<<1)&0xffffffff
 return c
def text(data):
 if data and data[0]<0x20:data=data[1:]
 return clean(data.decode('utf-8','replace'))[:120]
def parse_section(b):
 if len(b)<8:return {'error':'short section'}
 n=3+(((b[1]&15)<<8)|b[2]);b=b[:n]
 if len(b)!=n or n<12:return {'error':'invalid section length'}
 out={'table_id':b[0],'extension':int.from_bytes(b[3:5],'big'),'version':(b[5]>>1)&31,'current_next':b[5]&1,'section':b[6],'last_section':b[7],'crc_ok':crc32_mpeg(b)==0,'bytes':len(b)}
 if b[0]==0:
  out['programs']=[{'sid':int.from_bytes(b[p:p+2],'big'),'pmt_pid':((b[p+2]&31)<<8)|b[p+3]} for p in range(8,len(b)-4-3,4) if int.from_bytes(b[p:p+2],'big')]
 elif b[0] in (0x42,0x46):
  out['onid']=int.from_bytes(b[8:10],'big');services=[];p=11
  while p+5<=len(b)-4:
   sid=int.from_bytes(b[p:p+2],'big');length=((b[p+3]&15)<<8)|b[p+4];end=p+5+length
   if end>len(b)-4:break
   row={'sid':sid,'free_ca':bool(b[p+3]&16),'running_status':b[p+3]>>5};d=p+5
   while d+2<=end:
    tag,size=b[d:d+2];v=b[d+2:d+2+size]
    if len(v)!=size:break
    if tag==0x48 and len(v)>=3:
     row['service_type']=v[0];k=v[1];row['provider']=text(v[2:2+k]);pos=2+k
     if pos<len(v):row['name']=text(v[pos+1:pos+1+v[pos]])
    d+=2+size
   services.append(row);p=end
  out['services']=services
 elif b[0]==2:
  out['pcr_pid']=((b[8]&31)<<8)|b[9];p=12+(((b[10]&15)<<8)|b[11]);streams=[]
  while p+5<=len(b)-4:
   length=((b[p+3]&15)<<8)|b[p+4];streams.append({'type':b[p],'pid':((b[p+1]&31)<<8)|b[p+2]});p+=5+length
  out['streams']=streams
 return out
def section_probe(path,pid,table,seconds):
 # Only a new per-file-descriptor section filter. Never DMX_SET_SOURCE/PES/DVR.
 fd=os.open(path,os.O_RDWR|os.O_NONBLOCK);found=[];pending=b'';seen=set();read_errors=[]
 try:
  filtr=bytes([table])+bytes(15);mask=b'\xff'+bytes(15)
  params=struct.pack('H16s16s16s2xII',pid,filtr,mask,bytes(16),0,4)
  assert len(params)==60
  fcntl.ioctl(fd,0x403c6f2b,params);deadline=time.monotonic()+seconds
  while time.monotonic()<deadline and len(found)<24:
   if not select.select([fd],[],[],min(.2,max(0,deadline-time.monotonic())))[0]:continue
   try:data=os.read(fd,65536)
   except BlockingIOError:continue
   except OSError as e:
    read_errors.append({'errno':e.errno,'detail':str(e)[:100]})
    if e.errno==75:continue
    break
   if not data:break
   pending+=data
   while len(pending)>=3:
    n=3+(((pending[1]&15)<<8)|pending[2])
    if n>4096 or n<3:pending=pending[1:];continue
    if len(pending)<n:break
    raw,pending=pending[:n],pending[n:];digest=hashlib.sha256(raw).digest()
    if raw[0]==table and digest not in seen:seen.add(digest);found.append(parse_section(raw))
   if len(pending)>65536:pending=b''
  return {'node':path,'pid':pid,'table_id':table,'sections':found,'seconds':seconds,'read_errors':read_errors}
 finally:os.close(fd)
def worker():
 try:
  kind=sys.argv[2]
  if kind=='frontend':r=frontend(sys.argv[3])
  elif kind=='section':r=section_probe(sys.argv[3],int(sys.argv[4]),int(sys.argv[5]),float(sys.argv[6]))
  else:raise ValueError('Unknown worker')
 except Exception as e:r={'error':type(e).__name__,'detail':str(e)[:200]}
 print(json.dumps(r))
def bounded(args,timeout=5):
 # Separate child + file output: even a wedged driver ioctl cannot hold the report pipe.
 with tempfile.TemporaryFile() as f:
  try:
   p=subprocess.Popen(args,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
   try:p.wait(timeout=timeout)
   except subprocess.TimeoutExpired:
    try:os.killpg(p.pid,signal.SIGKILL)
    except OSError:pass
    try:p.wait(timeout=.3)
    except subprocess.TimeoutExpired:pass
    return {'timeout':True,'pid':p.pid,'note':'No further ioctl probes will be made on this frontend if it times out.'}
   f.seek(0);data=clean(f.read(524288).decode(errors='replace'))
   return {'returncode':p.returncode,'output':data}
  except OSError as e:return {'error':type(e).__name__,'detail':str(e)[:100]}
def job(kind,*args,timeout=6):
 global PROBE_STOPPED
 if PROBE_STOPPED:return {'skipped':'An earlier DVB ioctl probe exceeded its deadline.'}
 r=bounded([sys.executable,str(Path(__file__).resolve()),'--worker',kind]+list(map(str,args)),timeout)
 if r.get('timeout'):PROBE_STOPPED=True
 if 'output' in r:
  try:return json.loads(r['output'])
  except ValueError:return r
 return r
def filtered_log(s):
 pattern=re.compile(r'terrestrial|cxd|m88tc|dvb|frontend|\bpat\b|\bpmt\b|\bsdt\b|\bnit\b|scan|demux|\bts[01]\b|i2c|timeout|traceback|segfault|symbol|oops|panic',re.I)
 return '\n'.join(clean(x) for x in s.splitlines() if pattern.search(x))[-45000:]
def logs():
 out={};d=bounded(['dmesg'],4);out['kernel']=filtered_log(d.get('output','')) if 'output' in d else d
 paths=sorted(Path('/home/root/logs').glob('*enigma2*'),key=lambda p:p.stat().st_mtime,reverse=True)[:3]
 for p in paths:
  if not p.is_file():continue
  try:
   with p.open('rb') as f:f.seek(max(0,p.stat().st_size-750000));data=f.read(750000).decode(errors='replace')
   out[p.name]=filtered_log(data)
  except OSError:pass
 return out
def web():
 out={}
 for endpoint in ['signal','getcurrent']:
  try:
   data=urllib.request.urlopen('http://127.0.0.1/web/'+endpoint,timeout=2).read(65536);root=ET.fromstring(data)
   allowed={'e2snr','e2snrdb','e2ber','e2acg','e2frontendstatus','e2servicename','e2vpid','e2apid','e2onid','e2tsid'}
   out[endpoint]={e.tag:clean(e.text or '') for e in root.iter() if e.tag in allowed}
  except Exception as e:out[endpoint]={'error':type(e).__name__}
 return out
def database_summary():
 s=read('/etc/enigma2/lamedb',4000000)
 if '\nservices\n' not in s:return {'available':False}
 tail=s.split('\nservices\n',1)[1];rows=[x for x in tail.splitlines() if re.match(r'^[0-9a-fA-F]+:[0-9a-fA-F]{8}:',x)]
 return {'available':True,'services':len(rows),'terrestrial_services':sum(':eeee' in x.lower() for x in rows),'sha256':hashlib.sha256(s.encode()).hexdigest()}
def analyse(r):
 out=[]
 def add(code,level,msg):out.append({'code':code,'level':level,'message':msg})
 if not r['platform']['supported_model']:add('WRONG_MODEL','warning','This tool targets GTMedia GT Combo; active DVB probes were skipped on this model.')
 if not r['root']:add('NOT_ROOT','warning','Some device and log access requires root.')
 ts=r.get('terrestrial_frontends',[])
 observed=ts+[x['frontend'] for x in r.get('scan_window',[]) if isinstance(x.get('frontend',{}).get('systems'),list)]
 if not ts:add('NO_TERRESTRIAL_FRONTEND','error','No frontend advertised DVB-T/T2. Check module load, NIM registration and kernel ABI.')
 lock=any(x.get('status',{}).get('raw',0)&16 for x in observed)
 if ts and not lock:add('NO_FULL_RF_LOCK','warning','Signal percentage alone is not LOCK. Need a known active local frequency, correct DVB-T/T2, bandwidth, PLP and antenna input.')
 for f in ts:
  if f.get('status',{}).get('raw',0)&1 and not f.get('status',{}).get('raw',0)&16:add('SIGNAL_WITHOUT_LOCK','warning','The frontend sees energy but has not locked the multiplex.')
  if f.get('delivery_system') not in (3,16):add('WRONG_DELIVERY_SYSTEM','warning','Terrestrial frontend is not currently set to DVB-T or DVB-T2.')
  if isinstance(f.get('bandwidth_hz'),int) and f['bandwidth_hz'] not in (0,1712000,5000000,6000000,7000000,8000000,10000000):add('UNUSUAL_BANDWIDTH','warning','Review the current bandwidth against the local broadcaster.')
  if f.get('delivery_system')==16 and isinstance(f.get('stream_id'),int) and f['stream_id'] not in (0xffffffff,) and f['stream_id']>255:add('UNUSUAL_PLP','warning','DVB-T2 stream/PLP selection is unusual; compare with known local PLP IDs.')
 pats=[p for p in r.get('pat_probes',[])+r.get('pat_after_scan',[]) if any(x.get('crc_ok') and x.get('current_next') and x.get('programs') for x in p.get('sections',[]))]
 if lock and not pats:add('LOCK_BUT_NO_PAT','error','RF lock is present but no valid PAT reached tested demux nodes. TS0 pin configuration, TS clock/polarity, board wiring, demux routing or an inactive scan route are candidates; this is not proof of which one failed.')
 if pats:
  add('PAT_PRESENT','info','Valid program tables reached a demux. Check SDT/PMT and whether this is actually the terrestrial transport, not a still-routed satellite multiplex.')
  tables=r.get('tables',{})
  if 'sdt' in tables and not any(x.get('crc_ok') for x in tables.get('sdt',{}).get('sections',[])):add('PAT_WITHOUT_SDT','warning','Valid PAT but no valid actual SDT was captured; missing/wrong service descriptions can block discovery.')
  if tables.get('pmts') and not any(x.get('crc_ok') and x.get('streams') for p in tables['pmts'] for x in p.get('sections',[])):add('NO_VALID_PMT','warning','Program IDs were present but usable PMT stream descriptions were not captured.')
 for p in r.get('pat_probes',[]):
  if any(x.get('crc_ok') is False for x in p.get('sections',[])):add('CRC_ERRORS','warning','Invalid table CRCs were observed; investigate transport corruption and RF quality.')
 log=json.dumps(r.get('logs_after',{})).lower()
 if any(x in log for x in ['disagrees about version','unknown symbol','invalid module format']):add('MODULE_ABI_WARNING','error','Kernel log contains a module ABI/load error; inspect the exact relevant line.')
 if 'traceback' in log or 'segfault' in log:add('SCAN_OR_UI_EXCEPTION','warning','A Python exception or crash marker exists in the captured log; correlate timestamps with this scan.')
 before=r.get('database_before',{}).get('terrestrial_services',0);after=r.get('database_after',{}).get('terrestrial_services',0)
 if after>before:add('SERVICES_ADDED','info','Terrestrial service count increased during the test window.')
 if r.get('active_probe_timeout'):add('IOCTL_PROBE_TIMEOUT','error','A DVB ioctl probe exceeded its deadline. Active probes stopped; inspect the kernel log before repeating. A defective driver can remain blocked even after the child is killed.')
 if not lock and not pats:add('INCONCLUSIVE_STREAM_TEST','info','No locked terrestrial transport was available for a conclusive stream-path test. Repeat while tuned to the affected multiplex.')
 return out

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--watch',type=int,default=25);ap.add_argument('--quick',action='store_true');ap.add_argument('--output',default='/tmp/gt-terrestrial-report.json');a=ap.parse_args()
 a.watch=max(0,min(60,a.watch));target=Path(a.output)
 if target.is_symlink():raise SystemExit('Refusing symlink report output')
 model=read('/proc/device-tree/model').replace('\0','').strip();supported='gt' in model.lower() and 'combo' in model.lower()
 r={'tool':'GTMedia terrestrial diagnostic','version':VERSION,'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'root':os.geteuid()==0,'platform':{'model':model,'kernel':os.uname().release,'machine':os.uname().machine,'supported_model':supported},'safety':'No tuning/FE_SET_PROPERTY, module load/unload, I2C writes, route changes, deletion or reboot. Only bounded read queries and temporary per-FD PSI filters; report file is written locally. Does not upload anything.'}
 print('GTMedia terrestrial diagnostic. Keep the affected frequency selected in Signal Finder.',flush=True)
 r['psi_attribution']='PSI probes read the existing demux route; valid tables can belong to a different tuner. No source selection is forced.'
 r['nodes']=sorted(str(p) for p in Path('/dev/dvb').glob('adapter*/*'))
 r['modules']=clean('\n'.join(x for x in read('/proc/modules').splitlines() if re.search(r'gt_terrestrial|cxd|m88|dvb|demux|stream_input',x,re.I)))
 r['nim_sockets']=clean(read('/etc/gtcombo-nim-sockets') or read('/proc/bus/nim_sockets'))
 r['tuner_settings']=clean('\n'.join(x for x in read('/etc/enigma2/settings').splitlines() if x.startswith(('config.Nims.','config.terrestrial.','config.scan.'))))
 r['routes']={str(p):clean(read(p,4096).strip()) for p in Path('/sys/class/stb').glob('*') if re.fullmatch(r'(?:source|ts[0-3]|demux[0-3]_source|dvr[0-3]_mode|asyncfifo[0-3]_(?:source|flush_size))',p.name)}
 r['startup_service']=clean(read('/etc/init.d/gtcombo-terrestrial',16000));r['autoload_links']={str(p):os.readlink(p) for p in Path('/etc').glob('rc*.d/*terrestrial*') if p.is_symlink()}
 r['module_files']={}
 for name in ['gt-terrestrial.ko','m88rs6060.ko','aml_hardware_dmx.ko']:
  p=Path('/lib/modules')/os.uname().release/'extra'/name
  if p.is_file():
   raw=p.read_bytes();v=re.search(rb'vermagic=([^\0]{1,200})',raw)
   r['module_files'][str(p)]={'size':p.stat().st_size,'sha256':hashlib.sha256(raw).hexdigest(),'vermagic':v.group(1).decode(errors='replace') if v else None}
 r['database_before']=database_summary();r['web_before']=web();r['logs_before']=logs();r['frontends']=[];r['terrestrial_frontends']=[];timed_out=set()
 if supported:
  for p in list(Path('/dev/dvb').glob('adapter*/frontend*'))[:6]:
   f=job('frontend',p,timeout=8);f['node']=str(p);r['frontends'].append(f)
   if f.get('timeout'):timed_out.add(str(p));r['active_probe_timeout']=True;break
   if set(f.get('systems',[]) if isinstance(f.get('systems'),list) else []).intersection({3,16}):r['terrestrial_frontends'].append(f)
 r['pat_probes']=[]
 if supported and not a.quick and not r.get('active_probe_timeout'):
  print('Checking PAT on temporary section filters; no source routing is changed.',flush=True)
  nodes=list(Path('/dev/dvb').glob('adapter*/demux*'))[:4]
  for p in nodes:
   probe=job('section',p,0,0,1.4,timeout=4);r['pat_probes'].append(probe)
   if probe.get('timeout'):r['active_probe_timeout']=True;break
  good=next((p for p in r['pat_probes'] if any(s.get('crc_ok') and s.get('programs') for s in p.get('sections',[]))),None)
  if good and not r.get('active_probe_timeout'):
   node=good['node'];r['tables']={'sdt':job('section',node,17,0x42,2,timeout=4),'nit':job('section',node,16,0x40,1.5,timeout=4),'pmts':[]}
   programs=[x for s in good['sections'] if s.get('crc_ok') for x in s.get('programs',[])][:3]
   for p in programs:r['tables']['pmts'].append(job('section',node,p['pmt_pid'],2,1.2,timeout=4))
  print('NOW start the failing terrestrial scan using the remote. Monitoring for %d seconds...'%a.watch,flush=True)
  r['scan_window']=[];end=time.monotonic()+a.watch
  while time.monotonic()<end:
   for f in r['terrestrial_frontends'][:2]:
    if f['node'] in timed_out or r.get('active_probe_timeout'):continue
    sample=job('frontend',f['node'],timeout=4);r['scan_window'].append({'elapsed_utc':time.strftime('%H:%M:%S',time.gmtime()),'frontend':sample})
    if sample.get('timeout'):timed_out.add(f['node']);r['active_probe_timeout']=True
   time.sleep(min(2,max(0,end-time.monotonic())))
  # Repeat PAT after scan activation, since Signal Finder may not route the transport.
  r['pat_after_scan']=[]
  if not r.get('active_probe_timeout'):
   for p in nodes:
    probe=job('section',p,0,0,1.4,timeout=4);r['pat_after_scan'].append(probe)
    if probe.get('timeout'):r['active_probe_timeout']=True;break
   if not r.get('tables'):
    good=next((p for p in r['pat_after_scan'] if any(s.get('crc_ok') and s.get('programs') for s in p.get('sections',[]))),None)
    if good and not r.get('active_probe_timeout'):
     node=good['node'];r['tables']={'sdt':job('section',node,17,0x42,2,timeout=4),'nit':job('section',node,16,0x40,1.5,timeout=4),'pmts':[]}
     for pr in [x for ss in good['sections'] if ss.get('crc_ok') for x in ss.get('programs',[])][:3]:r['tables']['pmts'].append(job('section',node,pr['pmt_pid'],2,1.2,timeout=4))
 r['active_probe_timeout']=bool(r.get('active_probe_timeout') or PROBE_STOPPED)
 r['logs_after']=logs();r['web_after']=web();r['database_after']=database_summary();r['findings']=analyse(r)
 tmp=None
 try:
  fd,tmp=tempfile.mkstemp(prefix='.gt-terrestrial-report-',dir=str(target.parent));os.fchmod(fd,0o600)
  with os.fdopen(fd,'w') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
  os.replace(tmp,target);tmp=None
 finally:
  if tmp:os.unlink(tmp)
 print('\nREPORT: '+str(target),flush=True)
 print('Send ONLY this JSON report back. No passwords or commands are needed from the recipient.')
 for f in r['findings']:print(f['level'].upper()+': '+f['code']+' - '+f['message'])
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--worker':worker()
 else:main()
