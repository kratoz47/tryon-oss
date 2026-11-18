import sys,tempfile,threading,urllib.request,json,http.cookiejar,io,base64,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'local'))
import server
from user_store import UserStore
from PIL import Image
class GuestTests(unittest.TestCase):
 def test_guest_flow(self):
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
   server.account_store=UserStore(directory)
   http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Server);server.origin='http://127.0.0.1:'+str(http.server_port)
   threading.Thread(target=http.serve_forever,daemon=True).start()
   import http.cookiejar as cookiejar
   a=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar.CookieJar()))
   b=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar.CookieJar()))
   def req(c,path,payload=None):
    request=urllib.request.Request(server.origin+path,None if payload is None else json.dumps(payload).encode(),headers={'Origin':server.origin,'Content-Type':'application/json'})
    with c.open(request) as r:return json.load(r),r.headers
   try:
    one,headers=req(a,'/api/me');two,_=req(a,'/api/me');other,_=req(b,'/api/me')
    self.assertTrue(one['user']['guest']);self.assertFalse(one['login_required'])
    self.assertEqual(one['user']['id'],two['user']['id']);self.assertNotEqual(one['user']['id'],other['user']['id'])
    self.assertIn('HttpOnly',headers['Set-Cookie'])
    image=Image.new('RGB',(64,96),'white');buf=io.BytesIO();image.save(buf,'JPEG');photo='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()
    with patch.object(server.generation,'ready',return_value=True),patch.object(server.generation,'generate',return_value=image) as generate:
     for n in range(3):
      task,_=req(a,'/api/avatar',{'person':photo,'source':'face','appearance':'preserve','pose':'front','profile':{'build':'medium'},'provider':['seedream','fal','seedream'][n],'request_key':'guest-request-key-'+str(n)})
      self.assertEqual(task['provider'],['seedream','fal','seedream'][n])
      for _ in range(100):
       result,_=req(a,'/api/avatar?id='+task['id']+'&token='+task['token'])
       if result['status']=='completed':break
       time.sleep(.01)
      self.assertEqual(result['status'],'completed')
     used,_=req(a,'/api/me');self.assertIsNone(used['quota']['remaining']);self.assertTrue(used['quota']['unlimited']);self.assertEqual(used['quota']['used'],3);self.assertEqual(generate.call_count,3)
     with self.assertRaises(urllib.error.HTTPError):req(b,used['avatars'][0]['image_url'])
   finally:http.shutdown();http.server_close();server.account_store=None
if __name__=='__main__':unittest.main()
