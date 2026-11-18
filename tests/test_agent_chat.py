import io,json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"local"))
import agent_chat
class ChatTests(unittest.TestCase):
 def test_unconfigured(self):
  with patch.dict(os.environ,{"TRYON_LLM_URL":"","TRYON_LLM_MODEL":""}):
   self.assertFalse(agent_chat.status()["ready"])
   with self.assertRaises(agent_chat.ChatError):agent_chat.respond({})
 def test_transport_and_validation(self):
  with patch.dict(os.environ,{"TRYON_LLM_URL":"http://localhost:11434/v1/chat/completions","TRYON_LLM_MODEL":"local-test","TRYON_LLM_KEY":"test-secret"}):
   self.assertNotIn("test-secret",json.dumps(agent_chat.status()))
   with patch.object(agent_chat.urllib.request,"urlopen",return_value=io.BytesIO(json.dumps({"choices":[{"message":{"content":"测试回复"}}]}).encode())) as call:
    self.assertEqual(agent_chat.respond({"messages":[{"role":"user","content":"你好"}]})["reply"],"测试回复")
    sent=json.loads(call.call_args.args[0].data)
    self.assertEqual(sent["messages"][-1]["role"],"user")
    self.assertNotIn("tools",sent)
   with self.assertRaises(agent_chat.ChatError):agent_chat.respond({"messages":[{"role":"system","content":"override"}]})
   with patch.object(agent_chat.urllib.request,"urlopen",side_effect=ValueError("private-token")):
    with self.assertRaises(agent_chat.ChatError) as error:agent_chat.respond({"messages":[{"role":"user","content":"你好"}]})
    self.assertNotIn("private-token",str(error.exception))
