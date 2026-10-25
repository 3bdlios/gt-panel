#!/usr/bin/python3
from PIL import Image
import os,fcntl,threading,struct,zlib,ctypes,time
try:
 from cStringIO import StringIO
except ImportError:
 from io import BytesIO as StringIO
_capture_lock=threading.Lock()
_libc=ctypes.CDLL('libc.so.6',use_errno=True)
_libc.mmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_long]
_libc.mmap.restype=ctypes.c_void_p
_libc.munmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
_libc.munmap.restype=ctypes.c_int

def capture_image(width,height,osd,video,fmt,quality):
 if not _capture_lock.acquire(False):raise RuntimeError('A screenshot is already being captured')
 try:
  if video:
   fd=os.open('/dev/amvideocap0',os.O_RDONLY|os.O_NONBLOCK)
   mapped=None
   try:
    for nr,value in ((2,width),(3,height),(6,0)):fcntl.ioctl(fd,0x40045600|nr,value)
    fcntl.ioctl(fd,0x40085605,300)
    # The kernel submits a nonblocking GE2D conversion. A zero-byte read
    # triggers capture/cache invalidation without copying unfinished pixels.
    for attempt in range(8):
     try:os.read(fd,0);break
     except OSError as error:
      if error.errno!=11 or attempt==7:raise
      time.sleep(.05)
    mapped=_libc.mmap(None,width*height*3,1,1,fd,0)
    if mapped==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_errno(),'Cannot map video capture')
    time.sleep(.05);raw=ctypes.string_at(mapped,width*height*3)
    for attempt in range(6):
     time.sleep(.015);complete=ctypes.string_at(mapped,width*height*3)
     if complete==raw:break
     raw=complete
    else:raise RuntimeError('Video capture did not finish')
   finally:
    if mapped is not None and mapped!=ctypes.c_void_p(-1).value:_libc.munmap(mapped,width*height*3)
    os.close(fd)
   if len(raw)!=width*height*3:raise RuntimeError('Video capture returned an incomplete frame')
   image=Image.frombytes('RGB',(width,height),raw,'raw','BGR',0,1)
  else:image=Image.new('RGB',(width,height),(0,0,0))
  if osd:
   fbw,fbh=[int(x) for x in open('/sys/class/graphics/fb0/virtual_size').read().strip().split(',')]
   stride=int(open('/sys/class/graphics/fb0/stride').read().strip())
   fd=os.open('/dev/fb0',os.O_RDONLY)
   try:raw=os.read(fd,stride*fbh)
   finally:os.close(fd)
   if len(raw)!=stride*fbh:raise RuntimeError('UI capture returned an incomplete frame')
   layer=Image.frombytes('RGBA',(fbw,fbh),raw,'raw','BGRA',stride,1)
   if layer.size!=(width,height):layer=layer.resize((width,height),Image.BILINEAR)
   image.paste(layer,(0,0),layer.split()[3])
  if fmt=='png':
   # Fast PNG without the old Pillow encoder's expensive adaptive filters.
   raw=image.tobytes('raw','RGB');stride=width*3
   data=b''.join(b'\x00'+raw[y*stride:(y+1)*stride] for y in range(height))
   def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
   return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(data,1))+chunk(b'IEND',b'')
  out=StringIO()
  image.save(out,{'jpg':'JPEG','bmp':'BMP','gif':'GIF'}[fmt],quality=quality)
  return out.getvalue()
 finally:_capture_lock.release()


if __name__=='__main__':
 import argparse,sys,signal
 parser=argparse.ArgumentParser(description='XCONN Amlogic video and UI capture')
 parser.add_argument('-q',action='store_true')
 parser.add_argument('-s',action='store_true',dest='stdout')
 parser.add_argument('-p',action='store_true')
 parser.add_argument('-j',type=int,default=None)
 parser.add_argument('-r',type=int,default=None)
 parser.add_argument('-o',action='store_true')
 parser.add_argument('-v',action='store_true')
 parser.add_argument('-i',type=int,default=0)
 parser.add_argument('filename',nargs='?')
 args=parser.parse_args()
 def deadline(signum,frame):raise RuntimeError('Screenshot deadline exceeded')
 signal.signal(signal.SIGALRM,deadline);signal.alarm(8)
 try:
  if args.i:raise RuntimeError('Secondary video capture is not available')
  fw,fh=[int(x) for x in open('/sys/class/graphics/fb0/virtual_size').read().strip().split(',')]
  width=max(160,min(1920,args.r or fw));height=max(16,min(1080,int(round(width*fh/float(fw)))))
  fmt='png' if args.p else ('jpg' if args.j is not None else 'bmp')
  lock=open('/tmp/xc-openwebif-capture.lock','a')
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  data=capture_image(width,height,not args.v,not args.o,fmt,max(1,min(100,args.j or 85)))
  if args.stdout:sys.stdout.buffer.write(data)
  else:
   with open(args.filename or '/tmp/screenshot.'+fmt,'wb') as out:out.write(data)
 except Exception as error:
  import traceback,json
  with open('/tmp/xc-openwebif-error.txt','w') as log:log.write(repr(sys.argv)+'\n'+str(os.environ.get('LD_PRELOAD',''))+'\n'+traceback.format_exc())
  print('XCONN screenshot: '+str(error),file=sys.stderr);sys.exit(1)
 finally:signal.alarm(0)
