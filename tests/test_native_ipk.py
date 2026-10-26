import copy,json,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from GTPanel import core,native_ipk
ITEMS=json.loads((ROOT/'tests/fixtures/native-ipk-items.json').read_text())
class NativeIPKTests(unittest.TestCase):
 def setUp(self):
  self.item=copy.deepcopy(ITEMS[0]);self.device={k:v[0] for k,v in self.item['compatibility'].items()}
  self.data=(ROOT/'repository'/native_ipk.TRUSTED[self.item['id']]['filename']).read_bytes()
 def test_v3_catalog_and_both_pins(self):
  core.validate({'schema':3,'items':ITEMS})
  for i in ITEMS:native_ipk.validate(i)
 def test_catalog_cannot_add_native_package_or_change_review(self):
  for key,value in [('id','unreviewed'),('sha256','0'*64),('size',123),('files',['/etc/passwd']),('min_engine',2)]:
   item=copy.deepcopy(self.item);item[key]=value
   with self.assertRaises(core.SafetyError):native_ipk.validate(item)
 def test_download_uses_verified_exact_bytes(self):
  with patch.object(core,'fetch',return_value=self.data):
   self.assertEqual(core.prepare(self.item,'3bdlios/gt-panel',self.device),{'__reviewed_native_ipk__':self.data})
  with patch.object(core,'fetch',return_value=self.data+b'x'):
   with self.assertRaises(core.SafetyError):core.prepare(self.item,'3bdlios/gt-panel',self.device)
 def test_prepare_rejects_other_device_before_download(self):
  with patch.object(core,'fetch') as fetch:
   with self.assertRaises(core.SafetyError):core.prepare(self.item,'3bdlios/gt-panel',{'model':'other'})
   fetch.assert_not_called()
 def test_install_requires_confirmation(self):
  with patch.object(native_ipk.subprocess,'run') as run:
   with self.assertRaises(core.SafetyError):core.install(self.item,{'__reviewed_native_ipk__':self.data},False)
   run.assert_not_called()
 def test_native_install_dispatches_only_fixed_opkg_install(self):
  with tempfile.TemporaryDirectory() as d,patch.object(core,'STATE',d),patch.object(core,'facts',return_value=self.device),patch.object(native_ipk.platform,'machine',return_value='aarch64'),patch.object(native_ipk.shutil,'which',return_value='/usr/bin/opkg'),patch.object(native_ipk.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)) as run:
   backup=core.install(self.item,{'__reviewed_native_ipk__':self.data},True)
   self.assertEqual(backup,'/etc/xc-streamrelay-backups')
   args=run.call_args.args[0];self.assertEqual(args[:3],['/usr/bin/opkg','--force-reinstall','install']);self.assertNotIn('shell',run.call_args.kwargs)
   self.assertFalse((pathlib.Path(d)/'install.lock').exists())
   self.assertEqual(list(pathlib.Path(d).rglob('*.ipk')),[])
   self.assertEqual(json.loads(next(pathlib.Path(d).rglob('native-install.json')).read_text())['status'],'installed')
 def test_native_install_failure_preserves_log_and_releases_lock(self):
  with tempfile.TemporaryDirectory() as d,patch.object(core,'STATE',d),patch.object(core,'facts',return_value=self.device),patch.object(native_ipk.platform,'machine',return_value='aarch64'),patch.object(native_ipk.shutil,'which',return_value='/usr/bin/opkg'),patch.object(native_ipk.subprocess,'run',return_value=types.SimpleNamespace(returncode=1)):
   with self.assertRaises(core.SafetyError):core.install(self.item,{'__reviewed_native_ipk__':self.data},True)
   self.assertFalse((pathlib.Path(d)/'install.lock').exists());self.assertTrue(list(pathlib.Path(d).rglob('install.log')))
 def test_generic_ipk_reader_still_rejects_maintainer_scripts(self):
  from GTPanel import ipk
  with self.assertRaises(ipk.IPKError):ipk.payload(self.data,set(self.item["files"]))
 def test_generic_protection_is_unchanged(self):
  for p in ['/etc/passwd','/boot/kernel.img','/usr/lib/gstreamer-1.0/libgstxcamlvideo.so']:
   with self.assertRaises(core.SafetyError):core.safe_path(p)
if __name__=='__main__':unittest.main()
