import ast,pathlib,types,unittest
class RestartTests(unittest.TestCase):
 def setup_case(self,done=False,fail=False):
  source=pathlib.Path(__file__).resolve().parents[1]/'src/GTHEVC/plugin.py';tree=ast.parse(source.read_text());start=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='start')
  self.exits=[];self.dialogs=[];self.applied=0;self.marked=False
  class Timer:
   def __init__(self):self.callback=[]
   def start(self,delay,once):self.delay=delay
  def install():
   self.applied+=1
   if fail:raise RuntimeError('Unknown driver')
   return 'Installed'
  def mark():self.marked=True
  def defer(work):
   def callbacks(success,failure):
    try:result=work()
    except Exception as error:return failure(error)
    return success(result)
   return types.SimpleNamespace(addCallbacks=callbacks)
  self.scope={'eTimer':Timer,'quitMainloop':self.exits.append,'deferToThread':defer,'repair':types.SimpleNamespace(AUTO_STATE=types.SimpleNamespace(exists=lambda:done),install=install,mark_auto_done=mark),'MessageBox':types.SimpleNamespace(TYPE_INFO=0,TYPE_ERROR=1)}
  exec(compile(ast.Module(body=[start],type_ignores=[]),'startup','exec'),self.scope)
  session=types.SimpleNamespace(openWithCallback=lambda *a,**kw:self.dialogs.append((a,kw)),open=lambda *a,**kw:self.dialogs.append((a,kw)))
  self.scope['start'](0,session);self.scope['_timer'].callback[0]()
 def test_success_full_reboot_after_notice_once(self):
  self.setup_case();self.assertTrue(self.marked);self.assertEqual(self.applied,1);self.assertEqual(self.exits,[])
  args,kw=self.dialogs[0];self.assertEqual(kw['timeout'],5);args[0](None);self.assertEqual(self.exits,[2])
 def test_failure_does_not_reboot_or_mark_complete(self):
  self.setup_case(fail=True);self.assertFalse(self.marked);self.assertEqual(self.exits,[]);self.assertIn('will not restart',self.dialogs[0][0][1])
 def test_completed_installation_does_not_repeat(self):
  self.setup_case(done=True);self.assertEqual(self.applied,0);self.assertEqual(self.dialogs,[]);self.assertEqual(self.exits,[])
if __name__=='__main__':unittest.main()
