import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
with app.db() as c, (app.ROOT/'data/observations.ndjson').open('w') as f:
 for r in c.execute('SELECT * FROM observations'):f.write(json.dumps(dict(r))+'\n')
print('Exported curated data for Hadoop Streaming. Use HDFS encryption zones in production.')
