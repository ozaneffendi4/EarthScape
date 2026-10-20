"""EarthScape: role-based climate ingestion, analytics and alert service."""
import os,json,sqlite3,secrets,hashlib,hmac,time,csv,io,math,base64,subprocess,threading
from pathlib import Path
from datetime import datetime,timezone
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from PIL import Image
import storage_pipeline
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from cryptography.fernet import Fernet
ROOT=Path(__file__).parent
HOME=Path(os.environ.get('EARTHSCAPE_DATA',str(ROOT/'runtime')));HOME.mkdir(exist_ok=True,parents=True)
KEY=HOME/'secret.key'
if not KEY.exists(): KEY.write_bytes(Fernet.generate_key());KEY.chmod(0o600)
KEY.chmod(0o600)
CIPHER=Fernet(KEY.read_bytes());DB=HOME/'earthscape.db';SESSIONS={};LOCK=threading.Lock();START=time.time();FAILURES={};METRICS={"requests":0,"errors":0,"total_ms":0};ANALYTICS_CACHE={};BACKUP_LOCK=threading.Lock()
def db():
 c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row;return c
def password(p,s):return hashlib.pbkdf2_hmac('sha256',p.encode(),s.encode(),310000).hex()
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY,salt TEXT,hash TEXT,role TEXT);CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY,day TEXT,station TEXT,temperature REAL,rainfall REAL,co2 REAL,source TEXT,timestamp TEXT, UNIQUE(timestamp,station,source));CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY,created TEXT,station TEXT,message TEXT,ack INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY,created TEXT,owner TEXT,subject TEXT,body TEXT,status TEXT DEFAULT 'Open');CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,created TEXT,actor TEXT,action TEXT);CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY,created TEXT,name TEXT,path TEXT,kind TEXT);CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,created TEXT,status TEXT,output TEXT,error TEXT);''')
  columns=[r[1] for r in c.execute('PRAGMA table_info(observations)')]
  if 'timestamp' not in columns:
   c.executescript("ALTER TABLE observations RENAME TO observations_legacy;CREATE TABLE observations(id INTEGER PRIMARY KEY,day TEXT,station TEXT,temperature REAL,rainfall REAL,co2 REAL,source TEXT,timestamp TEXT,UNIQUE(timestamp,station,source));INSERT INTO observations SELECT *,day||'T00:00:00+00:00' FROM observations_legacy;DROP TABLE observations_legacy;")
  c.execute('CREATE INDEX IF NOT EXISTS idx_observation_station_day ON observations(station,day)')
  c.execute('CREATE INDEX IF NOT EXISTS idx_alert_open ON alerts(ack)')
  for name,role in [('admin','admin'),('analyst','analyst'),('viewer','viewer')]:
   if not c.execute('SELECT 1 FROM users WHERE name=?',(name,)).fetchone():
    p=os.environ.get('EARTHSCAPE_'+name.upper()+'_PASSWORD') or secrets.token_urlsafe(16);s=secrets.token_hex(16)
    c.execute('INSERT INTO users VALUES(?,?,?,?)',(name,s,password(p,s),role))
    with (HOME/'initial_credentials.txt').open('a') as f:f.write(f'{name}: {p}\n')
    (HOME/'initial_credentials.txt').chmod(0o600)
  c.execute("INSERT OR IGNORE INTO settings VALUES('threshold','40')")
 if not count():ingest(json.loads((ROOT/'data/sample.json').read_text()),'system')
def count():
 with db() as c:return c.execute('SELECT COUNT(*) FROM observations').fetchone()[0]
def audit(actor,action):
 with db() as c:c.execute('INSERT INTO audit(created,actor,action) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),actor,action))
def validate(row):
 if not isinstance(row,dict):raise ValueError('Each record must be an object')
 dt=datetime.fromisoformat(str(row.get('timestamp') or row['day']).replace('Z','+00:00'))
 if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
 dt=dt.astimezone(timezone.utc);day=dt.date().isoformat();timestamp=dt.isoformat();station=str(row['station']).strip()
 if not station or len(station)>80:raise ValueError('Station required (maximum 80 characters)')
 vals=[]
 for key,lo,hi in [('temperature',-100,70),('rainfall',0,3000),('co2',100,3000)]:
  v=row.get(key);v=None if v in ['',None] else float(v)
  if v is not None and (not math.isfinite(v) or not lo<=v<=hi):raise ValueError('Invalid '+key)
  vals.append(v)
 if all(x is None for x in vals):raise ValueError('At least one measurement required')
 source=str(row.get('source','weather'))
 if source not in ['weather','sensor','satellite']:raise ValueError('Unknown source')
 return (day,station,*vals,source,timestamp)
def ingest(rows,actor):
 if not isinstance(rows,list) or len(rows)>20000:raise ValueError('Expected up to 20,000 records')
 good=[];errors=[]
 for i,r in enumerate(rows):
  try:good.append(validate(r))
  except (ValueError,KeyError,TypeError) as e:errors.append({'row':i+1,'error':str(e)})
 added=0
 with db() as c:
  threshold=float(c.execute("SELECT value FROM settings WHERE key='threshold'").fetchone()[0])
  for r in good:
   cur=c.execute('INSERT OR IGNORE INTO observations(day,station,temperature,rainfall,co2,source,timestamp) VALUES(?,?,?,?,?,?,?)',r);added+=cur.rowcount
   if cur.rowcount and r[2] is not None and r[2]>threshold:c.execute('INSERT INTO alerts(created,station,message) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),r[1],f'Temperature {r[2]:.1f} C exceeds {threshold:.1f} C'))
 # Encrypted archive is durable before HDFS synchronization. Failed transfers remain queued.
 for day in sorted(set(r[0][:7] for r in good)):
  p=HOME/'raw'/day;p.mkdir(parents=True,exist_ok=True);f=p/(secrets.token_hex(8)+'.json.enc');f.write_bytes(CIPHER.encrypt(json.dumps([r for r in good if r[0].startswith(day)]).encode()))
  storage_pipeline.queue_file(f,'/earthscape/raw/'+day+'/'+f.name,HOME)
 ANALYTICS_CACHE.clear()
 audit(actor,f'Ingest: {added} accepted, {len(errors)} rejected')
 return {'inserted':added,'rejected':errors,'duplicates':len(good)-added}
def analytics(station=''):
 cached=ANALYTICS_CACHE.get(station)
 if cached and time.time()-cached[0]<15:return cached[1]
 with db() as c:
  rows=[dict(r) for r in c.execute('SELECT * FROM observations WHERE (?="" OR station=?) ORDER BY day,id',(station,station))]
  stations=[r[0] for r in c.execute('SELECT DISTINCT station FROM observations ORDER BY station')]
 valid=[r for r in rows if r['temperature'] is not None];daily={}
 for r in valid:daily.setdefault(r['day'],[]).append(r['temperature'])
 series=[{'day':d,'temperature':round(float(np.mean(v)),2)} for d,v in sorted(daily.items())]
 forecast=[];mae=None;anomalies=[]
 if len(series)>=10:
  x=np.array([(datetime.fromisoformat(r['day'])-datetime.fromisoformat(series[0]['day'])).days for r in series]).reshape(-1,1);y=np.array([r['temperature'] for r in series]);cut=max(2,int(len(x)*.8))
  m=LinearRegression().fit(x[:cut],y[:cut]);mae=round(mean_absolute_error(y[cut:],m.predict(x[cut:])),3);m.fit(x,y)
  from datetime import timedelta
  forecast=[{'day':(datetime.fromisoformat(series[-1]['day'])+timedelta(days=i)).date().isoformat(),'temperature':round(float(m.predict([[int(x[-1,0])+i]])[0]),2)} for i in range(1,15)]
 if len(valid)>=20:
  features=np.array([[r[k] if r[k] is not None else np.nan for k in ['temperature','rainfall','co2']] for r in valid]);med=np.nanmedian(features,axis=0);med=np.nan_to_num(med,nan=0);features=np.where(np.isnan(features),med,features)
  flags=IsolationForest(random_state=42,contamination=.04,n_estimators=80).fit_predict(features);anomalies=[r for r,f in zip(valid,flags) if f==-1]
 paired=[r for r in valid if r['co2'] is not None];corr=None
 if len(paired)>2 and np.std([r['co2'] for r in paired])>0 and np.std([r['temperature'] for r in paired])>0:corr=round(float(np.corrcoef([r['temperature'] for r in paired],[r['co2'] for r in paired])[0,1]),3)
 result={'records':len(rows),'stations':stations,'mean':round(float(np.mean([r['temperature'] for r in valid])),2) if valid else None,'series':series,'forecast':forecast,'mae':mae,'anomalies':anomalies,'correlation':corr,'latest':list(reversed(rows[-100:])),'missing':sum(r[k] is None for r in rows for k in ['temperature','rainfall','co2']),'model':'LinearRegression + IsolationForest','trained_at':datetime.now(timezone.utc).isoformat()}
 ANALYTICS_CACHE[station]=(time.time(),result)
 modeldir=HOME/'models';modeldir.mkdir(exist_ok=True);(modeldir/(hashlib.sha256(station.encode()).hexdigest()[:12]+'.json')).write_text(json.dumps({k:result[k] for k in ['model','trained_at','mae','correlation','forecast']}))
 return result
def backup():
 with BACKUP_LOCK:
  p=HOME/'backups';p.mkdir(exist_ok=True);tmp=p/(secrets.token_hex(8)+'.tmp')
  with db() as c,sqlite3.connect(tmp) as dest:c.backup(dest)
  target=p/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)+'.db.enc');target.write_bytes(CIPHER.encrypt(tmp.read_bytes()));tmp.unlink();return target.name

def backup_loop():
 while True:
  time.sleep(3600)
  try:backup()
  except Exception as e:print('Backup failed:',e)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,value,cookie=None):
  if status>=500:METRICS['errors']+=1
  b=json.dumps(value,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(b)
 def user(self):
  cookie=self.headers.get('Cookie','');token=next((x.strip().split('=',1)[1] for x in cookie.split(';') if x.strip().startswith('sid=')),'');s=SESSIONS.get(token)
  if s and s['expires']>time.time():return s
  return None
 def do_GET(self):
  started=time.perf_counter()
  try:self.get()
  except (ValueError,KeyError,TypeError) as e:self.send(400,{'error':str(e)})
  except Exception as e:print('GET error:',e);self.send(500,{'error':'Unable to complete request'})
  finally:METRICS['requests']+=1;METRICS['total_ms']+=(time.perf_counter()-started)*1000
 def get(self):
  path=urlparse(self.path)
  if path.path in ['/','/app.js','/style.css']:
   f=ROOT/'static'/({'/':'index.html'}.get(path.path,path.path[1:]));self.send_response(200);self.send_header('Content-Type',{'html':'text/html','js':'text/javascript','css':'text/css'}[f.suffix[1:]]);self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(f.read_bytes());return
  u=self.user()
  if not u:return self.send(401,{'error':'Please sign in'})
  if path.path=='/api/pipeline':return self.send(200,storage_pipeline.status(HOME))
  if path.path=='/api/jobs':
   with db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 20')]
   return self.send(200,rows)
  if path.path=='/api/users':
   if u['role']!='admin':return self.send(403,{'error':'Administrator required'})
   with db() as c:rows=[dict(r) for r in c.execute('SELECT name,role FROM users')]
   return self.send(200,rows)
  if path.path=='/api/me':return self.send(200,{'name':u['name'],'role':u['role'],'csrf':u['csrf']})
  if path.path=='/api/analytics':return self.send(200,analytics(parse_qs(path.query).get('station',[''])[0]))
  if path.path=='/api/status':
   with db() as c:threshold=c.execute("SELECT value FROM settings WHERE key='threshold'").fetchone()[0]
   return self.send(200,{'uptime_seconds':round(time.time()-START),'storage':os.environ.get('EARTHSCAPE_STORAGE','local'),'threshold':float(threshold),'database_bytes':DB.stat().st_size,'records':count(),'metrics':METRICS,'average_response_ms':round(METRICS['total_ms']/max(1,METRICS['requests']),2)})
  if path.path in ['/api/alerts','/api/tickets','/api/audit','/api/assets']:
   table=path.path.split('/')[-1]
   if table=='audit' and u['role']!='admin':return self.send(403,{'error':'Administrator required'})
   with db() as c:
    query='SELECT * FROM '+table+(' WHERE owner=?' if table=='tickets' and u['role']!='admin' else '')+' ORDER BY id DESC LIMIT 200'
    rows=[dict(r) for r in c.execute(query,(u['name'],) if table=='tickets' and u['role']!='admin' else ())]
   return self.send(200,rows)
  self.send(404,{'error':'Not found'})
 def do_POST(self):
  try:self.post()
  except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:self.send(400,{'error':str(e)})
  except Exception as e:print(type(e).__name__,str(e));self.send(500,{'error':'Operation failed; inspect server log'})
 def post(self):
  path=urlparse(self.path).path;n=int(self.headers.get('Content-Length','0'))
  if n<0 or n>10_000_000:return self.send(413,{'error':'Maximum payload 10 MB'})
  body=json.loads(self.rfile.read(n) or b'{}')
  if path=='/api/login':
   ip=self.client_address[0];attempts=[t for t in FAILURES.get(ip,[]) if time.time()-t<300]
   if len(attempts)>=10:return self.send(429,{'error':'Too many failed sign-ins. Try again in five minutes.'})
   time.sleep(.15)
   with db() as c:r=c.execute('SELECT * FROM users WHERE name=?',(body.get('name'),)).fetchone()
   if not r or not hmac.compare_digest(password(str(body.get('password','')),r['salt']),r['hash']):
    FAILURES[ip]=attempts+[time.time()];return self.send(401,{'error':'Invalid credentials'})
   FAILURES.pop(ip,None)
   token=secrets.token_urlsafe(32);SESSIONS[token]={'name':r['name'],'role':r['role'],'expires':time.time()+3600,'csrf':secrets.token_urlsafe(24)};audit(r['name'],'Login')
   return self.send(200,{'role':r['role']},'sid='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600'+('; Secure' if os.environ.get('EARTHSCAPE_HTTPS')=='1' else ''))
  u=self.user()
  if not u:return self.send(401,{'error':'Please sign in'})
  if self.headers.get('X-CSRF-Token')!=u['csrf']:return self.send(403,{'error':'Invalid CSRF token'})
  if path=='/api/logout':
   for k,v in list(SESSIONS.items()):
    if v is u:del SESSIONS[k]
   return self.send(200,{},'sid=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict')
  if path in ['/api/settings','/api/backup','/api/ticket-status','/api/user'] and u['role']!='admin':return self.send(403,{'error':'Administrator required'})
  if path in ['/api/ingest','/api/asset','/api/ack','/api/process'] and u['role']=='viewer':return self.send(403,{'error':'Analyst or administrator required'})
  if path=='/api/user':
   name=str(body['name']).strip();pw=str(body['password']);role=body['role']
   if not name or len(name)>50 or role not in ['admin','analyst','viewer'] or len(pw)<10:raise ValueError('Valid name, role and password of at least 10 characters required')
   salt=secrets.token_hex(16)
   with db() as c:
    old=c.execute('SELECT role FROM users WHERE name=?',(name,)).fetchone()
    if old and old['role']=='admin' and role!='admin' and c.execute("SELECT count(*) FROM users WHERE role='admin'").fetchone()[0]<=1:raise ValueError('Cannot demote the last administrator')
    c.execute('INSERT OR REPLACE INTO users VALUES(?,?,?,?)',(name,salt,password(pw,salt),role))
   for token,sess in list(SESSIONS.items()):
    if sess['name']==name:SESSIONS.pop(token,None)
   audit(u['name'],'Account updated: '+name);return self.send(200,{'ok':True})
  if path=='/api/process':
   job=storage_pipeline.start_job(HOME,DB)
   audit(u['name'],'MapReduce job queued');return self.send(202,{'job':job})
  if path=='/api/ingest':
   rows=list(csv.DictReader(io.StringIO(body['csv']))) if 'csv' in body else body['rows'];return self.send(200,ingest(rows,u['name']))
  if path=='/api/settings':
   t=float(body['threshold'])
   if not -100<=t<=70:raise ValueError('Threshold must be between -100 and 70 C')
   with db() as c:c.execute("UPDATE settings SET value=? WHERE key='threshold'",(str(t),))
   audit(u['name'],'Threshold updated');return self.send(200,{'threshold':t})
  if path=='/api/backup':return self.send(200,{'file':backup()})
  if path=='/api/ack':
   with db() as c:c.execute('UPDATE alerts SET ack=1 WHERE id=?',(int(body['id']),))
   return self.send(200,{'ok':True})
  if path=='/api/ticket':
   subject=str(body['subject']).strip();message=str(body['body']).strip()
   if not subject or not message or len(subject)>120 or len(message)>5000:raise ValueError('Subject and message required; 120/5000 character limits')
   with db() as c:c.execute('INSERT INTO tickets(created,owner,subject,body) VALUES(?,?,?,?)',(datetime.now(timezone.utc).isoformat(),u['name'],subject,message))
   return self.send(200,{'ok':True})
  if path=='/api/ticket-status':
   if body['status'] not in ['Open','Resolved']:raise ValueError('Invalid status')
   with db() as c:c.execute('UPDATE tickets SET status=? WHERE id=?',(body['status'],int(body['id'])))
   return self.send(200,{'ok':True})
  if path=='/api/asset':
   raw=base64.b64decode(body['data'],validate=True)
   if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'II*\x00') or raw.startswith(b'MM\x00*')):raise ValueError('Only PNG or TIFF satellite assets accepted')
   try:
    with Image.open(io.BytesIO(raw)) as image:image.verify()
   except (OSError,ValueError) as e:raise ValueError('Invalid PNG or TIFF image') from e
   folder=HOME/'assets';folder.mkdir(exist_ok=True);p=folder/(secrets.token_hex(16)+'.enc');p.write_bytes(CIPHER.encrypt(raw))
   storage_pipeline.queue_file(p,'/earthscape/satellite/'+p.name,HOME)
   with db() as c:c.execute('INSERT INTO assets(created,name,path,kind) VALUES(?,?,?,?)',(datetime.now(timezone.utc).isoformat(),Path(body['name']).name,str(p),'satellite'))
   audit(u['name'],'Satellite asset stored');return self.send(200,{'ok':True})
  self.send(404,{'error':'Not found'})
if __name__=='__main__':
 init();storage_pipeline.start_worker(HOME,DB);threading.Thread(target=backup_loop,daemon=True).start();print('EarthScape running at http://127.0.0.1:8080; credentials:',HOME/'initial_credentials.txt',flush=True);ThreadingHTTPServer((os.environ.get('EARTHSCAPE_HOST','127.0.0.1'),int(os.environ.get('PORT','8080'))),Handler).serve_forever()
