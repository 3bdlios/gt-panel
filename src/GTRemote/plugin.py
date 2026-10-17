"""Standalone mobile remote on port 8088, using the installed OpenWebif."""
import os
import socket
import fcntl
import struct
import subprocess
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from .server import config

child=None

def start(reason,session=None,**kwargs):
    global child
    if reason==0 and session is not None and (child is None or child.poll() is not None):
        config()
        with open('/tmp/gt-remote.log','ab',buffering=0) as log:
            child=subprocess.Popen(['/usr/bin/python3','-B',os.path.join(os.path.dirname(__file__),'server.py')],
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,close_fds=True)

def shutdown(reason,**kwargs):
    global child
    if reason!=0 and child is not None:
        if child.poll() is None:child.terminate()
        child=None

def main(session,**kwargs):
    start(0,session)
    settings=config();urls=[]
    for iface in ('wlan0','eth0'):
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                data=fcntl.ioctl(sock.fileno(),0x8915,struct.pack('256s',iface.encode()))
                urls.append('http://'+socket.inet_ntoa(data[20:24])+':'+str(settings['port']))
        except OSError:pass
    session.open(MessageBox,'GT Remote\n\n'+('\n'.join(urls) or 'No network address yet.')+
        '\n\nOpen the address in Safari or Chrome.\nNo pairing code required.\nUses OpenWebif on port 80.',MessageBox.TYPE_INFO)

def Plugins(**kwargs):
    return [PluginDescriptor(name='GT Remote',description='Standalone mobile remote · port 8088',where=PluginDescriptor.WHERE_PLUGINMENU,fnc=main),
            PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART,fnc=start),
            PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART,fnc=shutdown)]
