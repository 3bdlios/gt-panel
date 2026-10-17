import unittest,sys,pathlib,tempfile,hashlib,json,copy,io,struct,zlib,tarfile
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from GTPanel import core,repairs
class RepairTests(unittest.TestCase):
    def setUp(self):self.item=json.loads((ROOT/'repository/manifest-v2.json').read_text())['items'][0]
    def test_real_catalog_valid(self):core.validate({'schema':2,'items':[self.item]})
    def test_repair_path_not_open_to_normal_item(self):
        with self.assertRaises(core.SafetyError):core.safe_path('/usr/lib/gtcombo/android-boot.py')
        core.safe_path('/usr/lib/gtcombo/android-boot.py',True)
        for path in ('/dev/env','/flash/cfgload','/etc/shadow','/etc/gt-panel/policy.json',core.BASE+'GTPanel/core.py'):
            with self.assertRaises(core.SafetyError):core.safe_path(path,True)
    def test_unknown_actions_and_missing_hashes(self):
        self.item['action']='shell'
        with self.assertRaises(core.SafetyError):repairs.validate(self.item)
        self.item['action']='repair';del self.item['targets'][self.item['files'][0]]['before']
        with self.assertRaises(core.SafetyError):repairs.validate(self.item)
    def fixture_env(self):
        values=self.item['checks'][1]['values']
        raw=b'\0'.join(k.encode()+b'='+v.encode() for k,v in values.items())+b'\0\0'
        raw=raw.ljust(65532,b'\0');return struct.pack('<I',zlib.crc32(raw)&0xffffffff)+raw
    def test_checks_reject_wrong_hardware_and_crc(self):
        self.item['targets']={};self.item['files']=[]
        self.item['checks']=[self.item['checks'][1]]
        device={k:v[0] for k,v in self.item['compatibility'].items()}
        data=self.fixture_env_for_values(self.item['checks'][0]['values'])
        with patch.object(core,'facts',return_value=device),patch('builtins.open',return_value=io.BytesIO(data)):
            repairs.preflight(self.item)
        bad=bytearray(data);bad[-1]^=1
        with patch.object(core,'facts',return_value=device),patch('builtins.open',return_value=io.BytesIO(bad)):
            with self.assertRaises(core.SafetyError):repairs.preflight(self.item)
        with patch.object(core,'facts',return_value={}):
            with self.assertRaises(core.SafetyError):repairs.preflight(self.item)
    def fixture_env_for_values(self,values):
        data=(b'\0'.join(k.encode()+b'='+v.encode() for k,v in values.items())+b'\0\0').ljust(65532,b'\0')
        return struct.pack('<I',zlib.crc32(data)&0xffffffff)+data
    def test_repair_install_mode_unknown_file_and_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);p=root/'repair/helper.py';p.parent.mkdir();p.write_bytes(b'old')
            device={k:v[0] for k,v in self.item['compatibility'].items()}
            i=copy.deepcopy(self.item);i['checks']=[];i['files']=[str(p)];i['targets']={str(p):{'before':[hashlib.sha256(b'old').hexdigest()],'sha256':hashlib.sha256(b'new').hexdigest(),'mode':0o755}}
            with patch.object(repairs,'DEFAULT_ROOTS',(str(p.parent)+'/',)),patch.object(core,'facts',return_value=device),patch.object(core,'STATE',str(root/'state')):
                folder=core.install(i,{str(p):b'new'},True)
                self.assertEqual(p.read_bytes(),b'new');self.assertEqual(p.stat().st_mode&0o777,0o755)
                core.restore(folder);self.assertEqual(p.read_bytes(),b'old');self.assertEqual(p.stat().st_mode&0o777,0o644)
                p.write_bytes(b'unreviewed')
                with self.assertRaises(core.SafetyError):core.install(i,{str(p):b'new'},True)
                p.write_bytes(b'old')
                with self.assertRaises(core.SafetyError):core.install(i,{str(p):b'tampered'},True)
    def test_published_bundle_matches_every_target(self):
        bundle=(ROOT/'repository/gtcombo-android-v1.tar.gz').read_bytes()
        self.assertEqual(hashlib.sha256(bundle).hexdigest(),self.item['sha256'])
        with tarfile.open(fileobj=io.BytesIO(bundle),mode='r:gz') as tf:
            entries=tf.getmembers();self.assertEqual({'/'+m.name for m in entries},set(self.item['files']))
            for member in entries:
                self.assertTrue(member.isfile())
                self.assertEqual(hashlib.sha256(tf.extractfile(member).read()).hexdigest(),self.item['targets']['/'+member.name]['sha256'])
if __name__=='__main__':unittest.main()

class BackupIntegrityTests(unittest.TestCase):
    def test_corrupt_backup_rejected_before_restoring(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);plugins=root/'Plugins';p=plugins/'Demo/test';p.parent.mkdir(parents=True);p.write_bytes(b'old')
            with patch.object(core,'BASE',str(plugins)+'/'),patch.object(core,'STATE',str(root/'state')):
                folder=core.install({'id':'backup-test','files':[str(p)]},{str(p):b'new'},True)
                (pathlib.Path(folder)/'0').write_bytes(b'corrupt')
                with self.assertRaises(core.SafetyError):core.restore(folder)
                self.assertEqual(p.read_bytes(),b'new')
