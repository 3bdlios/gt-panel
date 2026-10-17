import importlib.util,json,threading,unittest,urllib.request,urllib.error
from pathlib import Path
spec=importlib.util.spec_from_file_location('remote',Path(__file__).resolve().parents[1]/'src/GTRemote/server.py');remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
class RemoteTests(unittest.TestCase):
 def setUp(self):
  self.server=remote.RemoteServer(('127.0.0.1',0),{'port':8088});threading.Thread(target=self.server.serve_forever,daemon=True).start();self.base='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):self.server.shutdown();self.server.server_close()
 def post(self,path,data,cookie=None,origin=None):
  headers={'X-GT-Remote':'1','Content-Type':'application/json'}
  if cookie:headers['Cookie']=cookie
  if origin:headers['Origin']=origin
  req=urllib.request.Request(self.base+path,json.dumps(data).encode(),headers)
  try:return urllib.request.urlopen(req)
  except urllib.error.HTTPError as error:return error
 def test_guard(self):
  self.assertEqual(self.post('/api/key',{'code':999}).code,400)
  self.assertEqual(self.post('/api/key',{'code':352},origin='http://evil.example').code,403)
  self.assertEqual(self.post('/api/pair',{'pin':'123456'}).code,404)
 def test_forward_exact_keys(self):
  paths=[];original=remote.Handler.upstream
  def fake(handler,path,data=None):paths.append(path);handler.send(200,{'result':True})
  remote.Handler.upstream=fake
  try:
   self.assertEqual(self.post('/api/key',{'code':352,'long':True}).code,200)
   self.post('/api/text',{'text':'hello & عربي'})
   self.assertEqual(paths[0],'/api/remotecontrol?command=352&type=long');self.assertIn('text=hello+%26+',paths[1])
  finally:remote.Handler.upstream=original
 def test_direct_access_and_assets(self):
  with urllib.request.urlopen(self.base+'/api/status') as response:self.assertTrue(json.load(response)['ready'])
  with urllib.request.urlopen(self.base+'/') as response:
   html=response.read();self.assertIn(b'GT Remote',html);self.assertNotIn(b'pairForm',html)
   self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
if __name__=='__main__':unittest.main()
