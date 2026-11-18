import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'local'))
import generation as g
class RoutingTests(unittest.TestCase):
 def test_explicit_routing(self):
  with patch.object(g.ark_generation,'ready',return_value=True),patch.object(g.fal_generation,'ready',return_value=True),patch.object(g.ark_generation,'generate',return_value='seed') as seed,patch.object(g.fal_generation,'generate',return_value='fal') as fal:
   self.assertEqual(g.generate(None,[],'prompt','fal'),'fal');seed.assert_not_called()
   self.assertEqual(g.generate(None,[],'prompt','seedream'),'seed');self.assertEqual(fal.call_count,1)
 def test_no_fallback(self):
  with patch.object(g.fal_generation,'ready',return_value=False),patch.object(g.ark_generation,'generate') as seed:
   with self.assertRaises(g.GenerationError):g.generate(None,[],'prompt','fal')
   seed.assert_not_called()
 def test_invalid_provider(self):
  with self.assertRaises(ValueError):g.validate('unknown')
if __name__=='__main__':unittest.main()
