import unittest,sys,tempfile,os,json,sqlite3
from pathlib import Path
# The unit runner imports test_project first and gives app an isolated directory.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import app,storage_pipeline
class StreamProcessingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):app.init()
 def test_multiple_sensor_readings_same_station(self):
  rows=[{'day':'2026-10-01T10:00:00Z','station':'StreamTest','temperature':24,'source':'sensor'},{'day':'2026-10-01T10:00:05Z','station':'StreamTest','temperature':25,'source':'sensor'}]
  r=app.ingest(rows,'test');self.assertEqual(r['inserted'],2);self.assertEqual(app.ingest(rows,'test')['duplicates'],2)
 def test_timezone_normalization(self):
  r=app.validate({'timestamp':'2026-10-01T03:00:00+05:00','station':'TimeTest','temperature':22});self.assertEqual(r[0],'2026-09-30');self.assertEqual(r[-1],'2026-09-30T22:00:00+00:00')
 def test_non_object_record_rejected(self):self.assertEqual(len(app.ingest(['bad'],'test')['rejected']),1)
 def test_finite_measurement_required(self):
  with self.assertRaises(ValueError):app.validate({'day':'2026-10-01','station':'NaN','temperature':float('nan')})
 def test_backup_unique_names(self):self.assertNotEqual(app.backup(),app.backup())
 def test_hdfs_outbox_idempotency(self):
  from unittest.mock import patch
  home=Path(tempfile.mkdtemp());f=home/'raw.enc';f.write_bytes(b'fixture')
  with patch.dict(os.environ,{'EARTHSCAPE_STORAGE':'hdfs'}):
   storage_pipeline.queue_file(f,'/earthscape/test/raw.enc',home);storage_pipeline.queue_file(f,'/earthscape/test/raw.enc',home)
   self.assertEqual(len(list((home/'outbox').glob('*.json'))),1)
 def test_local_processing_worker(self):
  job=storage_pipeline.start_job(app.HOME,app.DB);storage_pipeline.run_job(app.HOME,app.DB,job)
  with app.db() as c:r=c.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
  self.assertEqual(r['status'],'Completed');self.assertIn('Local',json.loads(r['output'])['engine'])
if __name__=='__main__':unittest.main(verbosity=2)
