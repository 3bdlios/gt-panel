#!/bin/sh
set -eu
command -v python3 >/dev/null 2>&1 || { echo 'Python3 is required'; exit 1; }
python3 - <<'PY'
import os, re, json, shutil, subprocess, time, tempfile
from pathlib import Path
VERSION='1.0'
report={'tool':'XCONN Wi-Fi diagnostic','version':VERSION,'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'changes':'Read-only diagnostics; writes this report only. No network restart or repair.','root':os.geteuid()==0,'findings':[]}
findings=report['findings']
def finding(code,level,message):findings.append({'code':code,'level':level,'message':message})
def read(path,limit=131072):
 try:return Path(path).read_text(errors='replace')[:limit]
 except OSError:return ''
def redact(s):
 s=re.sub(r'(?im)^.*(?:ssid|psk|password|passphrase|identity|private_key|wep_key)\s*[:=].*$', '[NETWORK_OR_SECRET_LINE_REDACTED]',s)
 s=re.sub(r'(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}','[MAC]',s)
 s=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[IPv4]',s)
 s=re.sub(r'(?i)\b(?:[0-9a-f]{0,4}:){2,}[0-9a-f:]*\b','[IPv6]',s)
 return s[:10000]
def run(args,timeout=4):
 if not shutil.which(args[0]):return {'available':False}
 try:
  p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout,encoding='utf-8',errors='replace')
  return {'available':True,'returncode':p.returncode,'output':redact(p.stdout)}
 except subprocess.TimeoutExpired:return {'available':True,'timeout':True}
 except OSError as e:return {'available':True,'error':type(e).__name__}
report['platform']={'model':redact(read('/proc/device-tree/model').replace('\0','').strip()),'kernel':os.uname().release}
report['tools']={name:shutil.which(name) is not None for name in ('wpa_supplicant','wpa_cli','iw','iwconfig','ip','rfkill','ifup','udhcpc')}
report['wpa_version']=run(['wpa_supplicant','-v'])
processes=[]
for p in Path('/proc').glob('[0-9]*'):
 comm=read(p/'comm').strip()
 if comm in ('wpa_supplicant','NetworkManager','connmand','iwd','udhcpc','dhcpcd','avahi-daemon'):
  processes.append({'pid':int(p.name),'name':comm})
report['processes']=processes
wpa_running=any(p['name']=='wpa_supplicant' for p in processes)
if not report['tools']['wpa_supplicant']:finding('WPA_EXECUTABLE_MISSING','error','wpa_supplicant executable not found in PATH.')
elif not wpa_running:finding('WPA_NOT_RUNNING','warning','No wpa_supplicant process at capture time; this does not identify why startup failed.')
interfaces=[]
for p in Path('/sys/class/net').glob('*'):
 if not ((p/'wireless').exists() or (p/'phy80211').exists() or p.name.startswith(('wlan','wlx'))):continue
 name=p.name
 if not re.fullmatch(r'[A-Za-z0-9_.:-]+',name):continue
 driver=p/'device/driver'
 entry={'name':name,'state':read(p/'operstate').strip(),'driver':driver.resolve().name if driver.exists() else None,'carrier':read(p/'carrier').strip(),'link':run(['ip','link','show','dev',name]),'wireless':run(['iw','dev',name,'info']),'association':run(['iw','dev',name,'link'])}
 if report['tools']['wpa_cli']:
  # status is read-only; secret and network-identity lines are removed.
  entry['supplicant_status']=run(['wpa_cli','-i',name,'status'])
  entry['supplicant_ping']=run(['wpa_cli','-i',name,'ping'])
 if not entry['driver']:finding('DRIVER_LINK_MISSING','warning','No sysfs driver link for '+name+'; inspect driver/module availability.')
 interfaces.append(entry)
report['interfaces']=interfaces
if not interfaces:finding('NO_WIFI_INTERFACE','error','No Wi-Fi interface found in sysfs; inspect module, firmware and hardware detection.')
rf=[]
for p in Path('/sys/class/rfkill').glob('rfkill*'):
 e={k:read(p/k).strip() for k in ('type','soft','hard')};rf.append(e)
 if e.get('type')=='wlan' and ('1' in (e.get('soft'),e.get('hard'))):finding('RADIO_BLOCKED','error','Wi-Fi is blocked by rfkill.')
report['rfkill']=rf
# Only allowlisted settings and validity flags are retained; never copy a config.
configs=[]
paths=set(Path('/etc').glob('wpa_supplicant*.conf'))
paths.update(Path('/etc/wpa_supplicant').glob('*.conf'))
for path in sorted(paths):
 if path.is_symlink() and not path.exists():
  configs.append({'file':str(path),'broken_symlink':True});continue
 text=read(path)
 profiles=[]
 for block in re.findall(r'(?ms)^\s*network\s*=\s*\{(.*?)^\s*\}',text):
  vals={m.group(1):m.group(2).strip() for m in re.finditer(r'(?m)^\s*(\w+)\s*=\s*(.*?)\s*$',block)}
  psk=vals.get('psk','')
  quoted=len(psk)>=2 and psk.startswith('"') and psk.endswith('"')
  valid=(quoted and 8<=len(psk[1:-1].encode())<=63) or bool(re.fullmatch('[0-9A-Fa-f]{64}',psk))
  safe={k:vals[k] for k in ('scan_ssid','disabled','priority','key_mgmt','proto','pairwise','group') if k in vals}
  # Do not trust arbitrary values in even allowlisted config keys.
  safe={k:v if re.fullmatch(r'[A-Za-z0-9_+ .-]{1,100}',v) else '[unrecognized]' for k,v in safe.items()}
  safe.update({'ssid_present':bool(vals.get('ssid')),'psk_present':bool(psk),'psk_format_valid':valid if psk else None,'wep_key_present':any(k.startswith('wep_key') for k in vals)})
  profiles.append(safe)
  if psk and not valid:finding('PSK_FORMAT_INVALID','error','A stored Wi-Fi PSK has an unexpected length/format; no key is included in report.')
 try:mode=oct(path.stat().st_mode & 0o777)
 except OSError:mode=None
 configs.append({'file':str(path),'readable':os.access(path,os.R_OK),'bytes':path.stat().st_size if path.exists() else None,'mode':mode,'profiles':profiles,'ctrl_interface_present':bool(re.search(r'(?m)^\s*ctrl_interface\s*=',text))})
report['configurations']=configs
if configs and not any(c.get('profiles') for c in configs):finding('NO_SAVED_PROFILE','warning','No network block found in inspected wpa_supplicant config files; a plugin may store profiles elsewhere.')
network=read('/etc/network/interfaces')
report['network_interfaces_config']={'wlan_stanzas':len(re.findall(r'(?m)^\s*iface\s+wl\S*',network)),'wpa_conf_paths':[]}
for s in re.findall(r'(?m)^\s*wpa-conf\s+(\S+)',network):
 if re.fullmatch(r'/etc/[A-Za-z0-9_./-]*wpa[A-Za-z0-9_./-]*\.conf',s):
  report['network_interfaces_config']['wpa_conf_paths'].append({'file':s,'exists':Path(s).exists()})
  if not Path(s).exists():finding('REFERENCED_CONFIG_MISSING','error','interfaces references a missing wpa-conf file.')
modules=read('/proc/modules')
report['wireless_modules']=[l.split()[0] for l in modules.splitlines() if re.search(r'(?i)cfg80211|mac80211|rtl|88x|8723|8189|brcm|dhd|mt76|wifi|wlan',l.split()[0])][:60]
# Logs are analyzed locally. Only fixed category names/counts leave the device.
patterns={
 'WPA_CONFIG_PARSE_ERROR':r'failed to read or parse configuration|failed to parse|invalid psk|line \d+:.*(?:invalid|failed|unknown)',
 'DRIVER_INITIALIZATION_FAILED':r'failed to initialize driver|driver does not support|could not configure driver|nl80211:.*(?:failed|not found|not supported)',
 'CONTROL_SOCKET_BUSY':r'ctrl_iface exists|address already in use|another wpa_supplicant',
 'WRONG_KEY_OR_HANDSHAKE':r'wrong_key|pre-shared key may be incorrect|4-way handshake failed|reason=wrong',
 'FIRMWARE_LOAD_FAILED':r'firmware.*(?:failed|not found|error)|direct firmware load.*failed',
 'RFKILL_LOG_ERROR':r'rfkill:.*(?:blocked|cannot|failed)',
 'AUTHENTICATION_REJECTED':r'ctrl-event-assoc-reject|ctrl-event-auth-reject',
 'CONNECTED_EVENT':r'ctrl-event-connected',
}
logcounts={k:0 for k in patterns}
log_sources=[]
logpaths=[Path('/var/log/messages'),Path('/var/log/syslog')]
for base in ('/tmp','/var/log','/home/root/logs'):
 for glob in ('*wpa*.log','*wifi*.log','*enigma2-debug.log'):
  logpaths.extend(sorted(Path(base).glob(glob),key=lambda p:p.stat().st_mtime,reverse=True)[:2])
for path in dict.fromkeys(logpaths):
 if not path.is_file():continue
 try:
  with path.open('rb') as f:
   f.seek(0,2);size=f.tell();f.seek(max(0,size-262144));data=f.read(262144).decode(errors='replace')
 except OSError:continue
 log_sources.append({'kind':'system' if path.name in ('messages','syslog') else 'wireless_or_gui','tail_bytes':min(size,262144)})
 for code,pattern in patterns.items():logcounts[code]+=len(re.findall(pattern,data,re.I))
try:
 p=subprocess.run(['dmesg'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=3,encoding='utf-8',errors='replace')
 for code,pattern in patterns.items():logcounts[code]+=len(re.findall(pattern,p.stdout[-262144:],re.I))
except (OSError,subprocess.TimeoutExpired):pass
report['log_analysis']={'raw_logs_included':False,'sources':log_sources,'category_counts':logcounts,'note':'Matches may describe earlier attempts, not necessarily the latest failure.'}
for code,count in logcounts.items():
 if count and code!='CONNECTED_EVENT':finding(code,'warning','Matching error pattern found in available logs; may be historical. Count: '+str(count))
report['limitations']=['No connection attempt, restart, scan, package install or settings change was performed.','A scan-visible network does not prove association or authentication will succeed.','Missing logs or inactive supplicant cannot alone determine the original failure.','PSK format check does not verify the actual password; escaped passphrases may need manual review.']
report['next_step']='Return this JSON report to the person diagnosing the image. Capture immediately after reproducing the Wi-Fi failure, before rebooting.'
fd,tmp=tempfile.mkstemp(prefix='xconn-wifi-report-',suffix='.tmp',dir='/tmp')
try:
 with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2,ensure_ascii=True);f.write('\n')
 os.replace(tmp,'/tmp/xconn-wifi-report.json')
finally:
 if os.path.exists(tmp):os.unlink(tmp)
print('REPORT: /tmp/xconn-wifi-report.json')
print('No Wi-Fi passwords, SSIDs, raw logs or MAC/IP addresses are intentionally included.')
for f in findings:print(f['level'].upper()+': '+f['code'])
PY
