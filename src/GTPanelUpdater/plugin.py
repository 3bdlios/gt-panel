from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from twisted.internet.threads import deferToThread
from enigma import eTimer
from . import updater
_BUSY=False
_AUTO_TIMER=None

def main(session,**kwargs):
    if _BUSY:
        session.open(MessageBox,'تحديث البنل جارٍ بالفعل.',MessageBox.TYPE_INFO)
        return
    session.openWithCallback(lambda yes:begin(session,yes),MessageBox,
        'تحديث GT Panel إلى 2.2.0؟\nيضيف دعم إصلاح ستريم ريلي وصورة IPTV.\nتُحفظ نسخة من البنل الحالي وتُعاد الواجهة تلقائيًا.',
        MessageBox.TYPE_YESNO,default=False)

def begin(session,yes):
    global _BUSY
    if yes is not True:return
    _BUSY=True
    deferToThread(updater.install).addCallbacks(lambda path:success(session,path),lambda error:failed(session,error))

def success(session,path):
    # The pinned GT Panel IPK restarts the GUI itself; do not schedule a second
    # restart that could kill the next Enigma process.
    session.open(MessageBox,
        'تم تحديث GT Panel إلى 2.2.0.\nستُعاد الواجهة تلقائيًا.\nنسخة الرجوع: '+path,
        MessageBox.TYPE_INFO,timeout=10,close_on_any_key=False)

def failed(session,error):
    global _BUSY
    _BUSY=False
    session.open(MessageBox,str(getattr(error,'value',error)),MessageBox.TYPE_ERROR)

def sessionstart(reason,session=None,**kwargs):
    global _AUTO_TIMER
    if reason!=0 or session is None or updater.finished():return
    def run_once():
        try:
            if updater.claim_auto_attempt():begin(session,True)
        except Exception as error:failed(session,error)
    _AUTO_TIMER=eTimer()
    _AUTO_TIMER.callback.append(run_once)
    _AUTO_TIMER.start(12000,True)

def Plugins(**kwargs):
    entries=[PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART,fnc=sessionstart)]
    if not updater.finished():
        entries.append(PluginDescriptor(name='تحديث GT Panel',description='إعادة محاولة تحديث البنل إلى 2.2.0',where=PluginDescriptor.WHERE_PLUGINMENU,fnc=main))
    return entries
