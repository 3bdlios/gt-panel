from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from enigma import eRCInput,eActionMap,eTimer,getDesktop
import time
from .engine import Diagnostic
from .checks import PHASES
from .trial import recover as recover_trial
from .web import ensure_server,stop_server,local_addresses,PORT

class DiagnosticScreen(Screen):
    def __init__(self,session):
        w,h=getDesktop(0).size().width(),getDesktop(0).size().height()
        width,height=int(w*.9),int(h*.84)
        f=max(20,int(h*.033))
        self.skin='''<screen name="AddRemoteDiagnostic" position="center,center" size="%d,%d" title="Add Remote Diagnostic" backgroundColor="#101722">
        <widget name="status" position="30,30" size="%d,%d" font="Regular;%d" foregroundColor="#eaf1f5" backgroundColor="#101722" />
        <widget name="help" position="30,%d" size="%d,60" font="Regular;%d" foregroundColor="#28d4df" backgroundColor="#101722" />
        </screen>'''%(width,height,width-60,height-130,f,height-85,width-60,max(18,f-3))
        Screen.__init__(self,session)
        self['status']=Label('')
        self['help']=Label('Green / OK: Start     Blue: Browser link     Red / Exit: Close')
        self['actions']=ActionMap(['OkCancelActions','ColorActions'],{'ok':self.begin,'green':self.begin,'blue':self.browser_link,'red':self.cancel,'cancel':self.cancel},-2)
        self.test=None;self.error='';self.published=False
        self.web=None
        try:self.web=ensure_server()
        except Exception as e:self.error='Browser server unavailable: '+str(e)
        self.links=['http://%s:%d/'%(ip,PORT) for ip in local_addresses()]
        self.timer=eTimer()
        if hasattr(self.timer,'callback'):
            self.timer.callback.append(self.poll)
        else:
            self.timer_connection=self.timer.timeout.connect(self.poll)
        self.timer.start(100,False)
        self.onClose.append(self.cleanup)
        self.onLayoutFinish.append(self.refresh)

    def refresh(self):
        browser='\n'.join(self.links) if self.web and self.links else 'Browser server / network unavailable'
        if self.test and self.test.running:
            remaining=max(0,int(self.test.deadline-time.monotonic())+1)
            instructions={name:label for name,seconds,label in PHASES}
            instructions['native_trial']='اختبار ربط مؤقت: اضغط نفس زر الجولة الأولى من الجديد مرتين.\nNEW: press the FIRST tested button twice. Temporary mapping test.'
            text='IR DIAGNOSTIC — %d seconds\n\n%s\n\nInput events: %d\n\nسيعود التحكم تلقائيًا عند انتهاء الفحص.'%(remaining,instructions[self.test.phase],self.test.native_events)
        elif self.test and self.test.finished:
            text='اكتمل الفحص / Diagnostic complete\n\nReport: %s\n\nInput events: %d\nErrors: %d\n\nافتح من الجوال على نفس الشبكة:\n%s\nنزّل التقرير وشاركه على واتساب.'%(self.test.archive,self.test.native_events,len(self.test.errors),browser)
        else:
            text='Add Remote Diagnostic 1.2\n\nجهّز الريموت الجديد والأصلي ثم اضغط الأخضر.\nفحص لمدة 87 ثانية كحد أقصى مع بقاء هذه الشاشة ظاهرة.\nيتوقف التنقل بالريموت مؤقتًا ويعود تلقائيًا.\nيفحص التعريفات والاستقبال والتكرار وتحرير الزر.\nيجرب ربط رمز غير معرف مؤقتًا ثم يسترجعه.\n\nPrepare BOTH remotes, then press Green.\n\nافتح من متصفح الجوال:\n%s\n\nFares3nzi — https://t.me/fares3nzi'%browser
        if self.error:text+='\n\n'+self.error
        self['status'].setText(text)

    def begin(self):
        if self.test and self.test.running:return
        self.session.openWithCallback(self.start,MessageBox,'بدء فحص IR؟\nسيتوقف التحكم بالريموت لمدة 87 ثانية كحد أقصى ثم يعود تلقائيًا.\nلا تختبر أثناء تسجيل مهم.\nيتضمن ربطًا مؤقتًا لرمز جديد غير معرف، ثم استرجاعه تلقائيًا.\nلا يغير أزرار الريموت الأصلي أو بروتوكولات الجهاز.\nبعد اكتماله نزّل التقرير من المتصفح.',type=MessageBox.TYPE_YESNO,default=False)

    def start(self,yes):
        if not yes:return
        self.error='';self.published=False
        try:
            self.test=Diagnostic(eRCInput.getInstance(),action=eActionMap.getInstance())
            self.test.start()
        except Exception as e:
            self.error='Diagnostic unavailable: '+str(e)
            if self.test:
                try:self.test.finish(cancelled=True)
                except Exception:pass
        self.refresh()

    def publish(self):
        if self.test and self.test.finished and not self.published and self.web:
            try:
                self.web.publish(self.test.archive)
                self.published=True
            except Exception as e:
                self.error='Report saved locally; browser publish failed: '+str(e)

    def poll(self):
        try:
            if self.test and self.test.running:self.test.tick()
            self.publish()
            self.refresh()
        except Exception as e:
            self.error=str(e)
            if self.test:
                try:self.test.finish(cancelled=True)
                except Exception as error:self.error+='; '+str(error)
            self.refresh()

    def browser_link(self):
        self.session.open(MessageBox,'افتح من الجوال على نفس شبكة الرسيفر:\n'+'\n'.join(self.links)+'\n\nنزّل ملف التقرير، ثم شاركه من التنزيلات إلى واتساب.\nلا يحتاج بريدًا أو رمز دخول.',type=MessageBox.TYPE_INFO)

    def cancel(self):
        if self.test and self.test.running:
            try:self.test.finish(cancelled=True)
            except Exception as e:self.error='Could not finish report: '+str(e)
            self.publish();self.refresh()
        else:self.close()

    def cleanup(self):
        self.timer.stop()
        try:
            if self.test and self.test.running:self.test.finish(cancelled=True)
        except Exception as e:self.error='Cleanup: '+str(e)
        self.publish()

def main(session,**kwargs):session.open(DiagnosticScreen)
def sessionstart(reason,**kwargs):
    if reason==1:stop_server()
    elif reason==0:
        try:recover_trial()
        except Exception as e:print('[AddRemoteDiagnostic] Recovery pending:',str(e))

def Plugins(**kwargs):return [PluginDescriptor(name='Add Remote Diagnostic',description='IR test and local browser reports',icon='plugin.png',where=PluginDescriptor.WHERE_PLUGINMENU,fnc=main),PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART,fnc=sessionstart)]
