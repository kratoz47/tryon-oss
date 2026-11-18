import base64, io, json, os, sys, unittest, urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'local'))
from PIL import Image
import ark_generation as ark

class Reply(io.BytesIO):
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

class ArkTests(unittest.TestCase):
 def setUp(self):
  self.image=Image.new('RGB',(32,48),'white')
  buf=io.BytesIO();self.image.save(buf,'JPEG')
  self.response=json.dumps({'data':[{'b64_json':base64.b64encode(buf.getvalue()).decode()}]}).encode()
 def test_request_and_output(self):
  def send(request,timeout):
   data=json.loads(request.data)
   self.assertEqual(request.full_url,ark.ENDPOINT)
   self.assertEqual(data['model'],ark.DEFAULT_MODEL)
   self.assertEqual(len(data['image']),7)
   self.assertNotIn('sequential_image_generation',data)
   self.assertNotIn('stream',data)
   self.assertEqual(data['model'],'doubao-seedream-5-0-flash-260915')
   self.assertEqual(data['response_format'],'b64_json')
   self.assertTrue(data['watermark'])
   return Reply(self.response)
  with patch.dict(os.environ,{'ARK_API_KEY':'test-only'}),patch('urllib.request.urlopen',side_effect=send) as call:
   self.assertEqual(ark.generate(self.image,[self.image]*6,'test').size,(32,48))
   self.assertEqual(call.call_count,1)
 def test_auth_error_is_sanitized_and_not_retried(self):
  with patch.dict(os.environ,{'ARK_API_KEY':'test-only'}),patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError(ark.ENDPOINT,403,'secret-detail',{},None)) as call:
   with self.assertRaisesRegex(ark.GenerationError,'未开通'):ark.generate(self.image,[],'test')
   self.assertEqual(call.call_count,1)
 def test_timeout_not_retried(self):
  with patch.dict(os.environ,{'ARK_API_KEY':'test-only'}),patch('urllib.request.urlopen',side_effect=TimeoutError) as call:
   with self.assertRaisesRegex(ark.GenerationError,'勿立即重复'):ark.generate(self.image,[],'test')
   self.assertEqual(call.call_count,1)
 def test_missing_result(self):
  with patch.dict(os.environ,{'ARK_API_KEY':'test-only'}),patch('urllib.request.urlopen',return_value=Reply(b'{"data":[]}')):
   with self.assertRaisesRegex(ark.GenerationError,'未返回'):ark.generate(self.image,[],'test')

if __name__=='__main__':unittest.main()
