"""Bounded read-only capture; Enigma2 owns lock/unlock, no runlevel changes."""
import fcntl
import json
import os
from pathlib import Path
import tarfile
import time
from .collector import EVENT, decode, metadata, read
from .checks import PHASES,inspect_devices,evaluate
from .trial import MappingTrial
from .lircprobe import LircProbe

class Diagnostic:
    def __init__(self, control, base='/tmp', duration=None, action=None):
        self.control = control
        self.duration = duration
        self.action=action
        self.trial=None
        self.lirc=None
        self.running=False
        self.phase_index=0
        self.phases=PHASES if duration is None else [('new_remote',duration,''),('pause',5,''),('original_remote',duration,'')]
        self.folder = Path(base)/('addremote-diagnostic-%d-%d-%d' % (time.time(),os.getpid(),time.monotonic_ns()%1000000))
        self.folder.mkdir(mode=0o700)
        self.info = metadata()
        (self.folder/'metadata.json').write_text(json.dumps(self.info,indent=2))
        (self.folder/'subsystem-checks.json').write_text(json.dumps(inspect_devices(self.info),indent=2))
        self.devices = {}
        self.locked = False
        self.output = None
        self.phase = None
        self.deadline = 0
        self.counts = {}
        self.errors = []
        self.native_events = 0
        self.records = 0
        self.archive = None
        self.finished = False

    def start(self):
        if self.control.islocked():raise OSError('Input is locked by another screen')
        try:
            self.control.lock()
            self.locked = True
            for device in self.info['devices']:
                fd = None
                try:
                    fd = os.open(device['node'],os.O_RDONLY|os.O_NONBLOCK)
                    # Verify exclusive ownership is free; immediately release our probe.
                    fcntl.ioctl(fd,0x40044590,1)
                    fcntl.ioctl(fd,0x40044590,0)
                    self.devices[fd] = device['node']
                    fd = None
                except OSError as e:
                    self.errors.append(device['node']+': '+str(e))
                finally:
                    if fd is not None:os.close(fd)
            self.lirc=LircProbe()
            if not self.devices and not self.lirc.devices:raise OSError('No accessible input or LIRC receiver after releasing GUI grab')
            (self.folder/'interrupts-before.txt').write_text(read('/proc/interrupts'))
            self.output = (self.folder/'events.jsonl').open('w')
            self.phase = self.phases[0][0]
            self.deadline = time.monotonic()+self.phases[0][1]
            self.running=True
        except Exception:
            self.close()
            raise

    def tick(self):
        if self.finished:return 'finished'
        if not self.running:return 'idle'
        now = time.monotonic()
        if self.lirc:self.lirc.tick(self.phase)
        for fd,path in list(self.devices.items()):
            try:
                data = os.read(fd,EVENT.size*128)
                if not data:raise OSError('Input device disconnected')
                events = decode(data)
                for event in events:
                    if self.records>=8192:break
                    event.update(phase=self.phase,device=path,monotonic=now)
                    self.output.write(json.dumps(event)+'\n')
                    self.records+=1
                    if event['type'] in (1,4):
                        key=self.phase+' '+path+' type='+str(event['type'])+' code='+str(event['code'])+' value='+str(event['value'])
                        self.counts[key]=self.counts.get(key,0)+1
                        self.native_events+=1
                self.output.flush()
            except BlockingIOError:pass
            except (OSError,ValueError) as e:
                self.errors.append(path+': '+str(e));os.close(fd);del self.devices[fd]
        if now>=self.deadline:
            self.phase_index+=1
            if self.phase_index<len(self.phases):
                self.phase=self.phases[self.phase_index][0]
                self.deadline=now+self.phases[self.phase_index][1]
            elif self.phase!='native_trial' and self.action is not None:
                self.output.flush()
                self.trial=MappingTrial(self.action)
                try:
                    if self.trial.start(self.folder):
                        self.phase='native_trial';self.deadline=now+12
                        self.control.unlock();self.locked=False
                    else:self.finish();return 'finished'
                except Exception as e:
                    self.errors.append('Mapping trial: '+str(e));self.finish();return 'finished'
            else:
                self.finish();return 'finished'
        return self.phase

    def close(self):
        self.running=False
        if self.lirc:
            self.lirc.close()
            (self.folder/'lirc-reception.json').write_text(json.dumps({'phases':self.lirc.phases,'mode_status':self.lirc.errors},indent=2))
        if self.trial:
            try:self.trial.close()
            except Exception as e:self.errors.append('Trial recovery: '+str(e))
        for fd in list(self.devices):
            try:os.close(fd)
            except OSError as e:self.errors.append(str(e))
        self.devices={}
        if self.output:
            self.output.close();self.output=None
        if self.locked:
            self.control.unlock();self.locked=False

    def finish(self, cancelled=False):
        if self.finished:return self.archive
        self.close()
        (self.folder/'interrupts-after.txt').write_text(read('/proc/interrupts'))
        summary={'subsystem_evaluation':evaluate(self.folder),'native_mapping_trial':self.trial.result if self.trial else {'status':'not attempted'},'persistence_test':'not tested: requires separate save and reboot confirmation','counts':self.counts,'errors':self.errors,'cancelled':cancelled,
                 'records':self.records,'input_lock_restored':not self.locked,
                 'interpretation':'No input events does not prove IR hardware incompatibility. CEC/network/HID sources must be distinguished.'}
        (self.folder/'summary.json').write_text(json.dumps(summary,indent=2))
        self.archive=self.folder.with_suffix('.tar.gz')
        partial=self.archive.with_name(self.archive.name+'.partial')
        with tarfile.open(partial,'w:gz') as t:t.add(self.folder,arcname=self.folder.name)
        os.replace(partial,self.archive)
        self.finished=True
        return self.archive
