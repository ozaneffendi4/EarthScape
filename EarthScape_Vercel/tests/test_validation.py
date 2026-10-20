import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.analytics import validate,analyze
class ValidationTests(unittest.TestCase):
 def test_nan_rejected(self):
  with self.assertRaises(ValueError):validate({'day':'2026-01-01','station':'K','temperature':float('nan')})
 def test_timestamp_utc(self):
  r=validate({'timestamp':'2026-01-02T01:00:00+05:00','station':'K','temperature':30});self.assertEqual(r[-1],'2026-01-01T20:00:00+00:00')
 def test_seed_analytics(self):
  data=json.loads((Path(__file__).resolve().parents[1]/'data/sample.json').read_text());out=analyze(data,sorted({r['station'] for r in data}));self.assertEqual(out['records'],720);self.assertEqual(len(out['forecast']),14);self.assertEqual(len(out['anomalies']),29)
if __name__=='__main__':unittest.main()
