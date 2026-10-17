import ast
from pathlib import Path
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]

class RestartTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse((ROOT/'src/GTPanel/plugin.py').read_text())
        panel=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GTPanel')
        methods=[n for n in panel.body if isinstance(n,ast.FunctionDef) and n.name in ('installed','restart_gui','error')]
        self.calls=[]
        scope={'quitMainloop':lambda code:self.calls.append(code),'MessageBox':types.SimpleNamespace(TYPE_INFO=0,TYPE_ERROR=1)}
        exec(compile(ast.Module(body=methods,type_ignores=[]),'restart','exec'),scope)
        self.scope=scope
        class Status:
            def setText(self,text):self.text=text
        class Panel:
            alive=True
            busy=False
            def __getitem__(self,key):return self.status
        self.panel=Panel();self.panel.status=Status()
        self.dialogs=[]
        self.panel.session=types.SimpleNamespace(openWithCallback=lambda *args,**kw:self.dialogs.append((args,kw)),open=lambda *args,**kw:None)
        self.panel.restart_gui=types.MethodType(scope['restart_gui'],self.panel)
    def test_success_waits_for_info_dialog_then_clean_gui_exit(self):
        self.scope['installed'](self.panel,'/backup/example')
        self.assertEqual(self.calls,[])
        args,kw=self.dialogs[0]
        self.assertEqual(kw['timeout'],5)
        self.assertIn('/backup/example',args[2])
        self.assertTrue(self.panel.busy)
        args[0](None)
        self.assertEqual(self.calls,[3])
    def test_failure_does_not_restart(self):
        self.scope['error'](self.panel,Exception('Install failed'))
        self.assertFalse(self.panel.busy)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.dialogs,[])
    def test_closed_screen_does_not_restart(self):
        self.panel.alive=False
        self.scope['installed'](self.panel,'/backup/example')
        self.panel.restart_gui()
        self.assertEqual(self.dialogs,[])
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
