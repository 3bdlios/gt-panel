import importlib.util,json,threading,unittest,urllib.request,urllib.error
from pathlib import Path
spec=importlib.util.spec_from_file_location('remote',Path(__file__).resolve().parents[1]/'src/GTRemote/server.py');remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
class RemoteTests(unittest.TestCase):
 def setUp(self):
  self.server=remote.RemoteServer(('127.0.0.1',0),{'pin':'123456','secret':'test-secret','port':8088});threading.Thread(target=self.server.serve_forever,daemon=True).start();self.base='http://127.0.0.1:'+str(self.server.server_port);self.cookie='gtremote='+remote.session_token(self.server.settings)
 def tearDown(self):self.server.shutdown();self.server.server_close()
 def post(self,path,data,cookie=None,origin=None):
  headers={'X-GT-Remote':'1','Content-Type':'application/json'}
  if cookie:headers['Cookie']=cookie
  if origin:headers['Origin']=origin
  req=urllib.request.Request(self.base+path,json.dumps(data).encode(),headers)
  try:return urllib.request.urlopen(req)
  except urllib.error.HTTPError as error:return error
 def test_pair_and_guard(self):
  self.assertEqual(self.post('/api/key',{'code':352}).code,401)
  self.assertEqual(self.post('/api/pair',{'pin':'no'}).code,403)
  paired=self.post('/api/pair',{'pin':'123456'});self.assertEqual(paired.code,200);self.assertIn('HttpOnly',paired.headers['Set-Cookie'])
  self.assertEqual(self.post('/api/key',{'code':999},self.cookie).code,400)
  self.assertEqual(self.post('/api/key',{'code':352},self.cookie,'http://evil.example').code,403)
 def test_forward_exact_keys(self):
  paths=[];original=remote.Handler.upstream
  def fake(handler,path,data=None):paths.append(path);handler.send(200,{'result':True})
  remote.Handler.upstream=fake
  try:
   self.assertEqual(self.post('/api/key',{'code':352,'long':True},self.cookie).code,200)
   self.post('/api/text',{'text':'hello & عربي'},self.cookie)
   self.assertEqual(paths[0],'/api/remotecontrol?command=352&type=long');self.assertIn('text=hello+%26+',paths[1])
  finally:remote.Handler.upstream=original
 def test_limits_assets_and_tokens(self):
  for unused in range(5):self.assertEqual(self.post('/api/pair',{'pin':'wrong'}).code,403)
  self.assertEqual(self.post('/api/pair',{'pin':'123456'}).code,429)
  self.assertFalse(remote.valid_token(self.server.settings,'broken'))
  self.assertFalse(remote.valid_token(self.server.settings,remote.session_token(self.server.settings,1)))
  with urllib.request.urlopen(self.base+'/') as response:self.assertIn(b'GT Remote',response.read());self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
if __name__=='__main__':unittest.main()
