"""HEVC fix with explicit installation and restore; automatic first-start application and one full reboot."""
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from . import repair
from enigma import eTimer,quitMainloop
from twisted.internet.threads import deferToThread

_timer=None

def start(reason,session=None,**kwargs):
 global _timer
 if reason!=0 or session is None:return
 def apply_once():
  if repair.AUTO_STATE.exists():return
  def work():
   result=repair.install()
   repair.mark_auto_done()
   return result
  def success(result):
   session.openWithCallback(lambda answer:quitMainloop(2),MessageBox,
    result+"\nThe receiver will restart fully in 5 seconds.",type=MessageBox.TYPE_INFO,timeout=5,close_on_any_key=False)
  def failure(error):
   session.open(MessageBox,"HEVC repair failed; receiver will not restart.\n"+str(getattr(error,"value",error)),type=MessageBox.TYPE_ERROR)
  deferToThread(work).addCallbacks(success,failure)
 _timer=eTimer();_timer.callback.append(apply_once);_timer.start(10000,True)


def main(session,**kwargs):
 def selected(choice):
  if choice is None:return
  def confirmed(answer):
   if not answer:return
   try:message=choice[1]();kind=MessageBox.TYPE_INFO
   except Exception as error:message=str(error);kind=MessageBox.TYPE_ERROR
   session.open(MessageBox,message,type=kind)
  session.openWithCallback(confirmed,MessageBox,choice[0]+'?\nOnly the tested HEVC driver build is accepted. An original backup is kept. A full receiver reboot is required afterwards.',type=MessageBox.TYPE_YESNO,default=False)
 session.openWithCallback(selected,ChoiceBox,title='GT HEVC restart repair',list=[('Install HEVC restart repair',repair.install),('Restore original HEVC driver',repair.restore)])

def Plugins(**kwargs):
 return [PluginDescriptor(name='GT HEVC restart repair',description='Repair HEVC NULL DMA allocation panic / restore original',where=PluginDescriptor.WHERE_PLUGINMENU,fnc=main),PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART,fnc=start)]
