import unittest,sys,tempfile,os,json,subprocess
from pathlib import Path
os.environ['EARTHSCAPE_DATA']=tempfile.mkdtemp();sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import app
class ProjectTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):app.init()
 def test_seed(self):self.assertGreaterEqual(app.count(),720)
 def test_invalid_data(self):
  r=app.ingest([{'day':'bad','station':'X','temperature':200}],'test');self.assertEqual(len(r['rejected']),1)
 def test_duplicates(self):
  r=json.loads((app.ROOT/'data/sample.json').read_text())[0];self.assertEqual(app.ingest([r],'test')['duplicates'],1)
 def test_missing(self):
  r=app.ingest([{'day':'2026-10-01','station':'MissingTest','temperature':22}],'test');self.assertEqual(r['inserted'],1)
 def test_alert(self):
  app.ingest([{'day':'2026-10-01','station':'HotTest','temperature':45}],'test')
  with app.db() as c:self.assertIsNotNone(c.execute("SELECT * FROM alerts WHERE station='HotTest'").fetchone())
 def test_models(self):
  a=app.analytics('Karachi');self.assertEqual(len(a['forecast']),14);self.assertIsNotNone(a['mae']);self.assertGreater(len(a['anomalies']),0)
 def test_empty_station(self):self.assertEqual(app.analytics('Unknown')['records'],0)
 def test_password(self):self.assertNotEqual(app.password('secret','salt'),'secret');self.assertEqual(app.password('secret','salt'),app.password('secret','salt'))
 def test_backup(self):
  p=app.HOME/'backups'/app.backup();self.assertTrue(app.CIPHER.decrypt(p.read_bytes()).startswith(b'SQLite format 3'))
 def test_partition_encryption(self):
  p=next((app.HOME/'raw').rglob('*.enc'));self.assertTrue(json.loads(app.CIPHER.decrypt(p.read_bytes())))
 def test_mapreduce(self):
  lines='\n'.join(json.dumps(r) for r in [{'station':'X','day':'2026-01-01','temperature':20},{'station':'X','day':'2026-01-02','temperature':30}])
  m=subprocess.run([sys.executable,str(app.ROOT/'hadoop/mapper.py')],input=lines,text=True,capture_output=True,check=True)
  r=subprocess.run([sys.executable,str(app.ROOT/'hadoop/reducer.py')],input='\n'.join(sorted(m.stdout.splitlines()))+'\n',text=True,capture_output=True,check=True);self.assertIn('25.0000\t2',r.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
