"""Use Amlogic video plus OSD capture for OpenWebif on XCONN/GT Combo."""
import os
from Plugins.Plugin import PluginDescriptor

def sessionstart(reason,session=None,**kwargs):
 if reason!=0 or session is None:return
 try:
  with open('/proc/device-tree/model') as source:model=source.read().strip('\x00 \t\r\n')
  if model not in ('XCONN','GTMedia GT Combo'):return
  if not os.path.exists('/dev/amvideocap0'):return
  from Plugins.Extensions.OpenWebif.controllers.models import grab
  grab.GRAB_PATH=os.path.join(os.path.dirname(__file__),'capture.py')
  print('[GTScreenshot] Complete Amlogic video + OSD capture enabled for %s'%model)
 except Exception as error:print('[GTScreenshot] Native capture retained: %s'%error)

def Plugins(**kwargs):
 return [PluginDescriptor(name='GT Screenshot Repair',description='Capture complete Amlogic video and OSD',where=PluginDescriptor.WHERE_SESSIONSTART,fnc=sessionstart)]
