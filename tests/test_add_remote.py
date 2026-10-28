import hashlib,json,pathlib,sys,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from GTPanel import core,ipk

class AddRemoteTests(unittest.TestCase):
 def setUp(self):
  self.item=json.loads((ROOT/'repository/add-remote-0.3.1.item.json').read_text())
  self.data=(ROOT/'repository/enigma2-plugin-extensions-addremote_0.3.1_all-panel.ipk').read_bytes()
 def test_reviewed_file_inventory_and_checksum(self):
  self.assertEqual(hashlib.sha256(self.data).hexdigest(),self.item['sha256'])
  self.assertEqual(len(self.data),self.item['size'])
  core.validate({'schema':3,'items':[self.item]})
  payload=ipk.payload(self.data,set(self.item['files']))
  for path,data in payload.items():
   self.assertTrue(path.startswith(core.BASE+'AddRemote/'))
   core.safe_path(path)
   if path.endswith('.py'):
    compile(data,path,'exec')
    source=ROOT/'plugins/add-remote/src/Plugins/Extensions/AddRemote'/path.split('/AddRemote/')[1]
    self.assertEqual(source.read_bytes(),data)
 def test_engine_can_prepare_exact_release_bytes(self):
  device={k:v[0] for k,v in self.item['compatibility'].items()}
  with patch.object(core,'fetch',return_value=self.data):
   payload=core.prepare(self.item,'3bdlios/gt-panel',device)
   self.assertEqual(set(payload),set(self.item['files']))
  with patch.object(core,'fetch',return_value=self.data+b'bad'):
   with self.assertRaises(core.SafetyError):core.prepare(self.item,'3bdlios/gt-panel',device)
 def test_other_identity_rejected_before_download(self):
  with patch.object(core,'fetch') as fetch:
   with self.assertRaises(core.SafetyError):core.prepare(self.item,'3bdlios/gt-panel',{})
   fetch.assert_not_called()

if __name__=='__main__':unittest.main()
