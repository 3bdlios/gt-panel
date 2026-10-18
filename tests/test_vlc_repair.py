import copy,hashlib,io,json,pathlib,sys,tarfile,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from GTPanel import core,repairs

class VLCRepairTests(unittest.TestCase):
 def setUp(self):
  self.item=json.loads((ROOT/'repository/gtcombo-vlc-stream-1.0.0.tar.gz.item.json').read_text())
  self.bundle=(ROOT/'repository/gtcombo-vlc-stream-1.0.0.tar.gz').read_bytes()
  with tarfile.open(fileobj=io.BytesIO(self.bundle),mode='r:gz') as t:
   self.members=t.getmembers();self.payload={'/'+m.name:t.extractfile(m).read() for m in self.members}
 def test_catalogs_and_download_integrity(self):
  for name in ['manifest-v2.json','repository/manifest-v2.json']:
   d=core.validate(json.loads((ROOT/name).read_text()))
   self.assertEqual(next(x for x in d['items'] if x['id']==self.item['id']),self.item)
  self.assertEqual(len(self.bundle),self.item['size'])
  self.assertEqual(hashlib.sha256(self.bundle).hexdigest(),self.item['sha256'])
  self.assertEqual(set(self.payload),set(self.item['targets']))
  for m in self.members:
   self.assertTrue(m.isfile());p='/'+m.name
   self.assertEqual(m.mode,self.item['targets'][p]['mode'])
   self.assertEqual(hashlib.sha256(self.payload[p]).hexdigest(),self.item['targets'][p]['sha256'])
  self.assertEqual(len(self.payload),3)
 def test_device_scope(self):
  facts={k:v[0] for k,v in self.item['compatibility'].items()}
  self.assertTrue(core.compatible(self.item,facts))
  for k in facts:
   changed=dict(facts);changed[k]='other'
   self.assertFalse(core.compatible(self.item,changed))
 def test_transaction_restore_and_unknown_file_rejection(self):
  with tempfile.TemporaryDirectory() as temp:
   root=pathlib.Path(temp);dest=root/'targets';dest.mkdir();item=copy.deepcopy(self.item);item['checks']=[];item['targets']={};payload={};original={}
   for p,meta in self.item['targets'].items():
    q=dest/pathlib.Path(p).name;m=copy.deepcopy(meta)
    if not p.endswith('.so'):
     old=('original '+q.name).encode();q.write_bytes(old);q.chmod(0o644);original[str(q)]=old;m['before']=[hashlib.sha256(old).hexdigest()]
    item['targets'][str(q)]=m;payload[str(q)]=self.payload[p]
   item['files']=list(payload);facts={k:v[0] for k,v in item['compatibility'].items()}
   with patch.object(repairs,'DEFAULT_ROOTS',(str(dest)+'/',)),patch.object(core,'STATE',str(root/'state')),patch.object(core,'facts',return_value=facts):
    folder=core.install(item,payload,True)
    for p,data in payload.items():self.assertEqual(pathlib.Path(p).read_bytes(),data)
    core.restore(folder)
    for p,data in original.items():self.assertEqual(pathlib.Path(p).read_bytes(),data)
    self.assertFalse((dest/'libgt-ts-tee.so').exists())
    p=next(iter(original));pathlib.Path(p).write_bytes(b'unknown local edit')
    with self.assertRaises(core.SafetyError):core.install(item,payload,True)
    self.assertEqual(pathlib.Path(p).read_bytes(),b'unknown local edit')
    self.assertFalse((dest/'libgt-ts-tee.so').exists())

if __name__=='__main__':unittest.main()
