"""Durable HDFS outbox and real Hadoop Streaming job execution."""
import os,json,time,threading,sqlite3,subprocess,secrets,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).parent
WORK_LOCK=threading.Lock();JOB_LOCK=threading.Lock()
def hadoop_bin(name):
 home=os.environ.get('HADOOP_HOME');return str(Path(home)/'bin'/name) if home else name
def mode():return os.environ.get('EARTHSCAPE_STORAGE','local')
def queue_file(path,destination,home):
 if mode()!='hdfs':return
 folder=home/'outbox';folder.mkdir(exist_ok=True)
 identity=hashlib.sha256((str(path.resolve())+'|'+destination).encode()).hexdigest()[:24]
 if (home/'synced'/identity).exists() or (folder/(identity+'.json')).exists():return
 (folder/(identity+'.json')).write_text(json.dumps({'path':str(path.resolve()),'destination':destination,'attempts':0,'error':''}))
def status(home):
 items=[]
 for p in (home/'outbox').glob('*.json'):
  try:items.append(json.loads(p.read_text()))
  except Exception:pass
 return {'mode':mode(),'queued':len(items),'failed':sum(bool(x['error']) for x in items),'last_error':next((x['error'] for x in items if x['error']),''),'last_sync':(home/'last_sync.txt').read_text() if (home/'last_sync.txt').exists() else None}
def sync(home):
 if mode()!='hdfs':return
 with WORK_LOCK:
  for item in list((home/'outbox').glob('*.json')):
   r=json.loads(item.read_text())
   try:
    subprocess.run([hadoop_bin('hdfs'),'dfs','-mkdir','-p',str(Path(r['destination']).parent)],capture_output=True,check=True,timeout=30)
    subprocess.run([hadoop_bin('hdfs'),'dfs','-put','-f',r['path'],r['destination']],capture_output=True,check=True,timeout=90)
    receipts=home/'synced';receipts.mkdir(exist_ok=True);(receipts/item.stem).write_text(r['destination'])
    item.unlink();(home/'last_sync.txt').write_text(datetime.now(timezone.utc).isoformat())
   except Exception as e:
    r['attempts']+=1;r['error']=str(e)[:300];item.write_text(json.dumps(r));break

def start_job(home,dbpath):
 with sqlite3.connect(dbpath) as c:
  cur=c.execute('INSERT INTO jobs(created,status,output,error) VALUES(?,?,?,?)',(datetime.now(timezone.utc).isoformat(),'Queued','',''));job=cur.lastrowid
 return job

def run_job(home,dbpath,job):
 with JOB_LOCK:
  work=home/'jobs'/str(job);work.mkdir(parents=True,exist_ok=True)
  with sqlite3.connect(dbpath) as c:
   c.row_factory=sqlite3.Row;rows=[dict(r) for r in c.execute('SELECT * FROM observations')];c.execute("UPDATE jobs SET status='Running' WHERE id=?",(job,))
  source=work/'observations.ndjson';source.write_text('\n'.join(json.dumps(r) for r in rows)+'\n');logs=[]
  def run(args,stdin=None):
   (work/'progress.txt').write_text(' '.join(args))
   r=subprocess.run(args,input=stdin,text=True,capture_output=True,timeout=240);logs.append('$ '+' '.join(args)+'\n'+r.stdout+'\n'+r.stderr)
   if r.returncode:raise RuntimeError(r.stderr[-2000:] or 'Command failed')
   return r.stdout
  try:
   if mode()=='hdfs':
    dest='/earthscape/curated/job-'+str(job);out='/earthscape/analytics/job-'+str(job)+'-'+secrets.token_hex(4)
    run([hadoop_bin('hdfs'),'dfs','-mkdir','-p',dest]);run([hadoop_bin('hdfs'),'dfs','-put','-f',str(source),dest+'/observations.ndjson'])
    stream=list((Path(os.environ['HADOOP_HOME'])/'share/hadoop/tools/lib').glob('hadoop-streaming-*.jar'))[0]
    run([hadoop_bin('hadoop'),'jar',str(stream),'-D','mapreduce.job.reduces=2','-files',str(ROOT/'hadoop/mapper.py')+','+str(ROOT/'hadoop/reducer.py'),'-input',dest+'/observations.ndjson','-output',out,'-mapper','python3 mapper.py','-reducer','python3 reducer.py'])
    output=run([hadoop_bin('hdfs'),'dfs','-cat',out+'/part-*']);engine='Hadoop HDFS + YARN MapReduce'
   else:
    import sys
    mapped=run([sys.executable,str(ROOT/'hadoop/mapper.py')],source.read_text());output=run([sys.executable,str(ROOT/'hadoop/reducer.py')],'\n'.join(sorted(mapped.splitlines()))+'\n');engine='Local mapper/reducer execution'
   (work/'monthly.tsv').write_text(output);payload={'engine':engine,'groups':len(output.splitlines()),'summary':output,'input_records':len(rows)}
   with sqlite3.connect(dbpath) as c:c.execute("UPDATE jobs SET status='Completed',output=? WHERE id=?",(json.dumps(payload),job))
  except Exception as e:
   with sqlite3.connect(dbpath) as c:c.execute("UPDATE jobs SET status='Failed',error=? WHERE id=?",(str(e),job))
  finally:(work/'execution.log').write_text('\n'.join(logs))
def start_worker(home,dbpath):
 def loop():
  while True:
   try:
    sync(home)
    with sqlite3.connect(dbpath) as c:row=c.execute("SELECT id FROM jobs WHERE status='Queued' ORDER BY id LIMIT 1").fetchone()
    if row:run_job(home,dbpath,row[0])
   except Exception as e:print('Pipeline worker:',e,flush=True)
   time.sleep(3)
 with sqlite3.connect(dbpath) as c:c.execute("UPDATE jobs SET status='Queued' WHERE status='Running'")
 threading.Thread(target=loop,daemon=True).start()
