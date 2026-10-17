"""Ensure the published remote installs through GT Panel's strict IPK reader."""
import hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from GTPanel import core,ipk
class CatalogTests(unittest.TestCase):
 def test_remote_package_matches_both_catalogs(self):
  for name in ('manifest-v2.json','repository/manifest-v2.json'):
   doc=core.validate(json.loads((ROOT/name).read_text()));item=next(i for i in doc['items'] if i['id']=='gt-remote')
   self.assertEqual(item['category'],'Plugins')
   blob=(ROOT/'repository'/item['url'].rsplit('/',1)[1]).read_bytes()
   self.assertEqual(len(blob),item['size']);self.assertEqual(hashlib.sha256(blob).hexdigest(),item['sha256'])
   files=ipk.payload(blob,set(item['files']));self.assertEqual(len(files),6)
   for path,data in files.items():self.assertEqual(data,(ROOT/'src/GTRemote'/path.split('/GTRemote/',1)[1]).read_bytes())
if __name__=='__main__':unittest.main()
