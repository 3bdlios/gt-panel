#!/bin/sh
# Read-only GTMedia boot diagnostics; writes only a local sanitized report.
exec /usr/bin/python3 - "$@" <<'PY'
import datetime,hashlib,json,os,re,stat,struct,sys,zlib
from pathlib import Path
REPORT=Path('/tmp/gtmedia-boot-report.json')
ENV_SIZE=65536
EXPECTED=b'if test ${bootfromnand} = 1; then setenv bootfromnand 0; saveenv; else run bootfromsd; run bootfromusb; run bootfromemmc; fi; run storeboot'
report={'format':'gtmedia-boot-diagnostic-v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'read_only':True,'errors':[]}
def sha(data):return hashlib.sha256(data).hexdigest()
def text(path,limit=32768):
    with open(path,'rb') as f:return f.read(limit).decode('utf-8','replace').replace('\x00',' ').strip()
def capture(key,fn):
    try:report[key]=fn()
    except Exception as e:report['errors'].append({'section':key,'error':str(e)})
def redact(s):
    s=re.sub(r'(?i)(?:https?|ftp)://[^\s\x00]+','[URL REDACTED]',s)
    s=re.sub(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b','[MAC REDACTED]',s)
    s=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[IP REDACTED]',s)
    s=re.sub(r'(?i)((?:serialno|serial|ethaddr|mac|password|passwd|token|secret|key|uuid)\s*[=:]\s*)[^\s;]+',r'\1[REDACTED]',s)
    return s[:16384]
def environment():
    p=Path('/dev/env');st=p.stat()
    if not stat.S_ISBLK(st.st_mode):raise RuntimeError('/dev/env is not a block device')
    with p.open('rb',buffering=0) as f:raw=f.read(ENV_SIZE)
    if len(raw)!=ENV_SIZE:raise RuntimeError('Short environment read')
    valid=struct.unpack('<I',raw[:4])[0]==zlib.crc32(raw[4:])&0xffffffff
    result={'length':len(raw),'sha256':sha(raw),'crc_valid':valid,'selected_variables':{}}
    if not valid:return result
    end=raw.find(b'\x00\x00',4)
    if end<0:raise RuntimeError('Missing environment terminator')
    env={}
    for item in raw[4:end].split(b'\x00'):
        if b'=' not in item:raise RuntimeError('Malformed environment')
        k,v=item.split(b'=',1)
        if k in env:raise RuntimeError('Duplicate environment key')
        env[k]=v
    # No full environment dump: retain only boot flow and board identifiers.
    allowed=['bootcmd','bootfromnand','bootfromsd','bootfromusb','bootfromemmc','storeboot','storeargs','reboot_mode','aml_dt','upgrade_step','bootdelay','boot_source']
    for name in allowed:
        value=env.get(name.encode())
        if value is not None:result['selected_variables'][name]=redact(value.decode('utf-8','replace'))
    result['bootcmd_matches_tested_one_shot']=env.get(b'bootcmd')==EXPECTED
    result['one_shot_flag']=env.get(b'bootfromnand',b'<missing>').decode('ascii','replace')
    return result

def bootloader():
    p=Path('/dev/bootloader');st=p.stat()
    if not stat.S_ISBLK(st.st_mode):raise RuntimeError('/dev/bootloader is not a block device')
    with p.open('rb',buffering=0) as f:data=f.read(4194304)
    return {'bytes_read':len(data),'first_4MiB_sha256':sha(data)}

def nodes():
    r={}
    for name in ['/dev/env','/dev/bootloader','/dev/fb0','/dev/mmcblk0']:
        p=Path(name)
        try:
            st=p.stat();r[name]={'resolved':os.path.realpath(name),'block':stat.S_ISBLK(st.st_mode),'major':os.major(st.st_rdev),'minor':os.minor(st.st_rdev)}
        except OSError as e:r[name]={'error':str(e)}
    return r

def files():
    names=['/usr/lib/gtcombo/android-once.py','/usr/lib/gtcombo/android-boot.py','/usr/lib/gtcombo/boot-menu.py','/usr/lib/gtcombo/xc-dualboot-fb.py','/usr/bin/gtcombo-show-bootlogo.py','/etc/init.d/gtcombo-boot-menu','/usr/lib/enigma2/python/Plugins/SystemPlugins/GTAndroidBoot/plugin.py','/flash/cfgload','/flash/cfgload_env']
    r={}
    for name in names:
        p=Path(name)
        try:
            st=p.stat()
            if not stat.S_ISREG(st.st_mode) or st.st_size>1048576:r[name]={'skipped':'not regular or exceeds 1MiB'};continue
            data=p.read_bytes();decoded=data.decode('utf-8','replace')
            item={'size':len(data),'sha256':sha(data),'mode':oct(stat.S_IMODE(st.st_mode))}
            if name.endswith('android-once.py'):
                item['guard_lines']=[redact(l) for l in decoded.splitlines() if any(x in l for x in ['BOOT_SHA','BOOTCMD=','GTMedia','XCONN','expected_boot_sha','sm1_','os.major','os.minor'])][:35]
            elif name in ['/usr/lib/gtcombo/android-boot.py','/etc/init.d/gtcombo-boot-menu','/usr/lib/enigma2/python/Plugins/SystemPlugins/GTAndroidBoot/plugin.py']:item['source']=redact(decoded)
            elif name.startswith('/flash/'):
                item['android_once_present']='android.once' in decoded
                item['boot_flow_lines']=[redact(l) for l in decoded.splitlines() if any(t in l for t in ['android.once','bootfromnand','storeboot'])][:12]
            r[name]=item
        except OSError as e:r[name]={'error':str(e)}
    return r

def logs():
    r={}
    # Deliberately omit full crash logs, channels, OSCam configs, network config and env dumps.
    for name in ['/tmp/gt-boot-menu.log','/etc/gtcombo-android-last-request.log']:
        try:
            with open(name,'rb') as f:
                f.seek(0,2);length=f.tell();f.seek(max(0,length-32768));s=f.read().decode('utf-8','replace')
            lines=s.splitlines()
            r[name]={'tail':redact('\n'.join(lines[-70:]))}
        except OSError as e:r[name]={'error':str(e)}
    candidates=sorted(Path('/home/root/logs').glob('*enigma2-crash.log'),key=lambda p:p.stat().st_mtime,reverse=True)[:2]
    for p in candidates:
        try:
            with p.open('rb') as f:data=f.read(2*1024*1024)
            lines=data.decode('utf-8','replace').splitlines();keep=set()
            markers=['Traceback','GTAndroidBoot','android-once','android-boot','boot-menu','RuntimeError','ImportError','ModuleNotFoundError','AttributeError','TypeError','AssertionError','ASSERTION']
            for i,line in enumerate(lines):
                if any(x in line for x in markers):keep.update(range(max(0,i-1),min(len(lines),i+10)))
            selected=[lines[i] for i in sorted(keep)][:150]
            r[p.name]={'size':p.stat().st_size,'relevant_excerpt':redact('\n'.join(selected)),'read_limit':2*1024*1024}
        except OSError as e:r[p.name]={'error':str(e)}
    return r

if os.geteuid()!=0:print('STOP: run as root inside Enigma2');sys.exit(1)
capture('kernel',lambda:os.uname().release)
capture('model',lambda:text('/proc/device-tree/model',1024))
capture('compatible',lambda:text('/proc/device-tree/compatible',2048))
capture('dt_id',lambda:text('/proc/device-tree/coreelec-dt-id',1024))
capture('python',lambda:sys.version.split()[0])
capture('nodes',nodes)
capture('mounts',lambda:[{'device':l.split()[0],'mount':l.split()[1],'filesystem':l.split()[2],'options':l.split()[3]} for l in text('/proc/mounts').splitlines() if len(l.split())>=4 and l.split()[1] in ('/','/flash')])
capture('bootloader',bootloader)
capture('environment',environment)
capture('files',files)
capture('startup_links',lambda:[{'path':str(p),'target':os.readlink(p) if p.is_symlink() else '<not a symlink>'} for directory in ['/etc/rcS.d','/etc/rc3.d'] for p in Path(directory).glob('*boot*')])
capture('logs',logs)
try:
    from PIL import ImageFont
    ImageFont.truetype('/usr/share/fonts/valis_enigma.ttf',20)
    report['menu_dependencies']='Pillow/font OK'
except Exception as e:report['menu_dependencies']=str(e)
# Exclusive, no-follow creation avoids overwriting an existing report or following a symlink.
path=REPORT
if path.exists() or path.is_symlink():path=REPORT.with_name('gtmedia-boot-report-'+str(os.getpid())+'.json')
fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
with os.fdopen(fd,'w') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
print('REPORT_READY:',path)
print('Send this JSON file back. No boot setting was changed; no reboot requested.')
print('Section warnings:',len(report['errors']))
PY
