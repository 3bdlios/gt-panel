import ast
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from Plugins.Extensions.AddRemoteDiagnostic import trial,checks,lircprobe

class ExtendedTests(unittest.TestCase):
    def test_trial_maps_only_unknown_and_restores_with_delivery_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);state=folder/'state.json'
            events=[{'phase':'new_single','type':4,'code':4,'value':0x123,'device':'/dev/null'}]*3
            (folder/'events.jsonl').write_text('\n'.join(json.dumps(x) for x in events))
            keymap={0x123:0};action=Mock()
            with patch.object(trial,'STATE',state),patch.object(trial,'identity',return_value={'name':'test'}),patch.object(trial.glob,'glob',return_value=['/dev/null']),patch.object(trial,'get_key',side_effect=lambda fd,scan:keymap[scan]),patch.object(trial,'set_key',side_effect=lambda fd,scan,key:keymap.__setitem__(scan,key)):
                t=trial.MappingTrial(action)
                self.assertTrue(t.start(folder));self.assertEqual(keymap[0x123],108)
                self.assertEqual(t.callback(108,0),1)
                self.assertEqual(t.callback(111,0),0)
                t.close();self.assertEqual(keymap[0x123],0)
                self.assertTrue(t.result['restored']);self.assertEqual(t.result['enigma_delivery'],'observed')
                action.unbindAction.assert_called_once()

    def test_existing_keymap_is_never_changed(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            (folder/'events.jsonl').write_text('\n'.join(json.dumps({'phase':'new_single','type':4,'code':4,'value':1,'device':'/dev/null'}) for _ in range(3)))
            with patch.object(trial,'STATE',folder/'state'),patch.object(trial,'get_key',return_value=352),patch.object(trial,'set_key') as setter:
                t=trial.MappingTrial(Mock());self.assertFalse(t.start(folder));setter.assert_not_called()

    def test_lirc_raw_and_scancode_records_are_separate(self):
        with patch.object(lircprobe.glob,'glob',return_value=[]):p=lircprobe.LircProbe()
        p.feed('/dev/lirc0','mode2','new_single',struct.pack('=II',0x1000000|9000,4500))
        p.feed('/dev/lirc0','scancode','original_remote',struct.pack('=QHHIQ',1,0,9,108,0x123))
        self.assertEqual(p.phases['new_single /dev/lirc0 mode2']['samples'][0]['microseconds'],9000)
        self.assertEqual(p.phases['original_remote /dev/lirc0 scancode']['samples'][0]['keycode'],108)

    def test_gui_cleanup_does_not_crash_if_publish_fails(self):
        source=Path(__file__).resolve().parents[1]/'src/Plugins/Extensions/AddRemoteDiagnostic/plugin.py'
        tree=ast.parse(source.read_text());cls=next(x for x in tree.body if isinstance(x,ast.ClassDef))
        methods=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in ('publish','cleanup')]
        isolated=ast.Module(body=[ast.ClassDef(name='Screen',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
        namespace={};exec(compile(ast.fix_missing_locations(isolated),str(source),'exec'),namespace)
        screen=namespace['Screen']();screen.timer=Mock();screen.test=Mock(finished=True,running=False);screen.test.archive='/tmp/report';screen.web=Mock();screen.web.publish.side_effect=ValueError('path check failed');screen.published=False
        screen.cleanup()
        self.assertIn('browser publish failed',screen.error)

if __name__=='__main__':unittest.main()
