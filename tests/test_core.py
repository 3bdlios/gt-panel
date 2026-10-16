import unittest, sys, pathlib, tempfile, os, json, tarfile, io, hashlib
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from GTPanel import core
class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.doc=json.loads((pathlib.Path(__file__).resolve().parents[1]/'repository/manifest.json').read_text())
    def test_manifest(self): core.validate(self.doc)
    def test_duplicate(self):
        self.doc['items'].append(self.doc['items'][0])
        with self.assertRaises(core.SafetyError): core.validate(self.doc)
    def test_paths(self):
        for path in ('/etc/passwd','/usr/bin/enigma2','/usr/share/enigma2/GT-X/../skin.xml',core.BASE+'GTPanel/core.py','/boot/kernel','/usr/share/enigma2/MetrixHD/skin.xml'):
            with self.assertRaises(core.SafetyError): core.safe_path(path)
    def test_url_scope(self):
        for url in ('http://github.com/me/repo/releases/download/a/b','https://github.com/evil/repo/releases/download/a/b','https://raw.githubusercontent.com/me/repo-evil/main/x','https://github.com/me/repo/releases/download/a/b?x=1'):
            with self.assertRaises(core.SafetyError): core.github_url(url,'me/repo')
    def test_fail_closed(self):
        self.assertFalse(core.compatible(self.doc['items'][0],{}))
        with self.assertRaises(core.SafetyError): core.install(self.doc['items'][0],{},False)
    def test_hash_and_tar(self):
        item=self.doc['items'][0]; device={k:v[0] for k,v in item['compatibility'].items()}
        bundle=(pathlib.Path(__file__).resolve().parents[1]/'repository/demo-fixes.tar.gz').read_bytes()
        with patch.object(core,'fetch',return_value=bundle): self.assertEqual(set(core.prepare(item,'me/repo',device)),set(item['files']))
        with patch.object(core,'fetch',return_value=b'bad'):
            with self.assertRaises(core.SafetyError): core.prepare(item,'me/repo',device)
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w:gz') as tf:
            m=tarfile.TarInfo('usr/lib/enigma2/python/Plugins/Extensions/GTDemo/x'); m.type=tarfile.SYMTYPE; m.linkname='/etc/passwd'; tf.addfile(m)
        data=out.getvalue(); item.update(size=len(data),sha256=hashlib.sha256(data).hexdigest())
        with patch.object(core,'fetch',return_value=data):
            with self.assertRaises(core.SafetyError): core.prepare(item,'me/repo',device)
    def test_install_restore_and_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp); state=root/'state'; plugins=root/'Plugins'; plugins.mkdir(); dest=plugins/'GTDemo'; dest.mkdir(); old=dest/'old'; old.write_bytes(b'before'); new=dest/'new'
            item={'id':'test','files':[str(old),str(new)]}; payload={str(old):b'after',str(new):b'new'}
            with patch.object(core,'BASE',str(plugins)+'/'), patch.object(core,'STATE',str(state)):
                backup=core.install(item,payload,True)
                self.assertEqual(old.read_bytes(),b'after'); self.assertTrue(new.exists())
                core.restore(backup); self.assertEqual(old.read_bytes(),b'before'); self.assertFalse(new.exists())
                original=core.atomic
                def fail(path,data,mode):
                    if path==str(new): raise OSError('simulated disk failure')
                    return original(path,data,mode)
                with patch.object(core,'atomic',side_effect=fail):
                    with self.assertRaises(OSError): core.install(item,payload,True)
                self.assertEqual(old.read_bytes(),b'before'); self.assertFalse(new.exists())
    def test_symlink_target(self):
        with tempfile.TemporaryDirectory() as temp:
            p=pathlib.Path(temp); (p/'GTDemo').symlink_to('/etc',target_is_directory=True)
            with patch.object(core,'BASE',temp+'/'):
                with self.assertRaises(core.SafetyError): core.safe_path(temp+'/GTDemo/passwd')
if __name__=='__main__': unittest.main()
