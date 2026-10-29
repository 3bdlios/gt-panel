"""Per-file-descriptor LIRC read modes only; never alter protocol filters."""
import fcntl
import glob
import os
import struct

class LircProbe:
    def __init__(self):
        self.devices=[];self.errors=[];self.phases={}
        for path in glob.glob('/dev/lirc[0-9]*'):
            for kind,mode in (('mode2',4),('scancode',8)):
                fd=None
                try:
                    fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
                    value=bytearray(4);fcntl.ioctl(fd,0x80046900,value,True)
                    if not struct.unpack('=I',value)[0] & (mode<<16):
                        raise OSError('Mode not declared by receiver')
                    fcntl.ioctl(fd,0x40046912,struct.pack('=I',mode))
                    fcntl.ioctl(fd,0x80046902,value,True)
                    if struct.unpack('=I',value)[0]!=mode:raise OSError('Receive mode verification failed')
                    self.devices.append((fd,path,kind));fd=None
                except OSError as e:self.errors.append(path+' '+kind+': '+str(e))
                finally:
                    if fd is not None:os.close(fd)

    def tick(self,phase):
        for fd,path,kind in list(self.devices):
            try:
                data=os.read(fd,4096 if kind=='mode2' else 24*128)
                if not data:raise OSError('LIRC disconnected')
                self.feed(path,kind,phase,data)
            except BlockingIOError:pass
            except (OSError,ValueError,struct.error) as e:
                self.errors.append(path+' '+kind+': '+str(e));os.close(fd);self.devices.remove((fd,path,kind))

    def feed(self,path,kind,phase,data):
        key=phase+' '+path+' '+kind
        result=self.phases.setdefault(key,{'records':0,'samples':[]})
        if kind=='mode2':
            if len(data)%4:raise ValueError('Partial MODE2 word')
            for (word,) in struct.iter_unpack('=I',data):
                result['records']+=1
                if len(result['samples'])<1024:result['samples'].append({'type':word>>24,'microseconds':word&0xffffff})
        else:
            if len(data)%24:raise ValueError('Partial scancode record')
            for timestamp,flags,protocol,keycode,scan in struct.iter_unpack('=QHHIQ',data):
                result['records']+=1
                if len(result['samples'])<256:result['samples'].append({'flags':flags,'protocol':protocol,'keycode':keycode,'scan_hex':'%x'%scan})

    def close(self):
        for fd,path,kind in self.devices:
            try:os.close(fd)
            except OSError as e:self.errors.append(str(e))
        self.devices=[]
