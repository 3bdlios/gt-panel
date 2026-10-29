import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from Plugins.Extensions.AddRemoteDiagnostic import collector,engine

class Tests(unittest.TestCase):
    def test_signed_scan_and_partial_record(self):
        result=collector.decode(collector.EVENT.pack(1,2,4,4,-1))
        self.assertEqual(result[0]['scan_hex'],'ffffffff')
        with self.assertRaises(ValueError):collector.decode(b'x')

    def test_failed_start_restores_input_lock(self):
        c=Mock();c.islocked.return_value=False
        with tempfile.TemporaryDirectory() as d,patch.object(engine,'metadata',return_value={'devices':[]}):
            test=engine.Diagnostic(c,base=d,duration=20)
            with self.assertRaises(OSError):test.start()
            c.lock.assert_called_once();c.unlock.assert_called_once()
            self.assertFalse(test.locked)

    def test_foreign_lock_not_changed(self):
        c=Mock();c.islocked.return_value=True
        with tempfile.TemporaryDirectory() as d,patch.object(engine,'metadata',return_value={'devices':[]}):
            test=engine.Diagnostic(c,base=d,duration=20)
            with self.assertRaises(OSError):test.start()
            c.lock.assert_not_called();c.unlock.assert_not_called()

    def test_phases_complete_and_report_restores_lock(self):
        c=Mock()
        with tempfile.TemporaryDirectory() as d,patch.object(engine,'metadata',return_value={'devices':[]}):
            test=engine.Diagnostic(c,base=d,duration=20)
            test.locked=True;test.running=True;test.phase='new_remote';test.deadline=10;test.output=io.StringIO()
            with patch.object(engine.time,'monotonic',return_value=11):self.assertEqual(test.tick(),'pause')
            with patch.object(engine.time,'monotonic',return_value=17):self.assertEqual(test.tick(),'original_remote')
            with patch.object(engine.time,'monotonic',return_value=38):self.assertEqual(test.tick(),'finished')
            c.unlock.assert_called_once()
            self.assertTrue(test.archive.exists())
            self.assertTrue(json.loads((test.folder/'summary.json').read_text())['input_lock_restored'])

if __name__=='__main__':unittest.main()
