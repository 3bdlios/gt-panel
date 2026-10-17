import importlib.util,pathlib,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hevc_repair',ROOT/'src/GTHEVC/repair.py');repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)
class HEVCTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name)
  self.module=self.root/'driver.ko';self.backup=self.root/'state'/'original.ko'
  # Use deterministic byte fixtures while preserving the real patch instruction and offset.
  self.original=b'X'*repair.OFFSET+bytes.fromhex('68020035')+b'unchanged tail'
  self.fixed=self.original[:repair.OFFSET]+bytes.fromhex('600200b5')+self.original[repair.OFFSET+4:]
  self.module.write_bytes(self.original)
  for name,value in [('MODULE',self.module),('BACKUP',self.backup),('ORIGINAL',repair.digest(self.original)),('FIXED',repair.digest(self.fixed))]:
   p=patch.object(repair,name,value);p.start();self.addCleanup(p.stop)
  p=patch.object(repair,'verify_host');p.start();self.addCleanup(p.stop)
 def test_backup_install_idempotent_restore(self):
  repair.install();self.assertEqual(self.backup.read_bytes(),self.original);self.assertEqual(self.module.read_bytes(),self.fixed)
  repair.install();self.assertEqual(self.backup.read_bytes(),self.original)
  repair.restore();self.assertEqual(self.module.read_bytes(),self.original)
 def test_unknown_driver_is_not_modified(self):
  self.module.write_bytes(b'unknown')
  with self.assertRaises(RuntimeError):repair.install()
  self.assertEqual(self.module.read_bytes(),b'unknown');self.assertFalse(self.backup.exists())
 def test_bad_backup_prevents_install_and_restore(self):
  self.backup.parent.mkdir();self.backup.write_bytes(b'corrupt')
  with self.assertRaises(RuntimeError):repair.install()
  self.assertEqual(self.module.read_bytes(),self.original)
  self.module.write_bytes(self.fixed)
  with self.assertRaises(RuntimeError):repair.restore()
  self.assertEqual(self.module.read_bytes(),self.fixed)
 def test_exact_patch_only_and_branch_target(self):
  result=repair.patched(self.original);self.assertEqual(result,self.fixed)
  before=int.from_bytes(self.original[repair.OFFSET:repair.OFFSET+4],'little');after=int.from_bytes(result[repair.OFFSET:repair.OFFSET+4],'little')
  self.assertEqual((before>>5)&0x7ffff,(after>>5)&0x7ffff)
  self.assertEqual(after&31,0);self.assertEqual(after>>31,1)
if __name__=='__main__':unittest.main()
