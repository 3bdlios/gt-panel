"""HEVC fix with explicit installation and restore; startup never changes the driver."""
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from . import repair

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
 return [PluginDescriptor(name='GT HEVC restart repair',description='Repair HEVC NULL DMA allocation panic / restore original',where=PluginDescriptor.WHERE_PLUGINMENU,fnc=main)]
