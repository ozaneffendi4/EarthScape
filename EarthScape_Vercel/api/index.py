"""EarthScape hosted edition: request-scoped Python API for Vercel."""
import os,sys,json,secrets,hashlib,hmac,time,csv,io,math,base64
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs,quote
from http.cookies import SimpleCookie
from cryptography.fernet import Fernet
from PIL import Image,UnidentifiedImageError

"""Server-only Supabase REST client. No database keys reach the browser."""
import json,os,urllib.request,urllib.error
class DatabaseError(Exception):pass
class Database:
 def __init__(self):
  self.url=os.environ.get('SUPABASE_URL','').rstrip('/')
  self.key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
  if not self.url.startswith('https://') or not self.key:raise DatabaseError('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Vercel, then redeploy.')
 def request(self,path,method='GET',data=None,prefer=None):
  headers={'apikey':self.key,'Authorization':'Bearer '+self.key,'Content-Type':'application/json','Accept':'application/json'}
  if prefer:headers['Prefer']=prefer
  req=urllib.request.Request(self.url+'/rest/v1/'+path,data=json.dumps(data,allow_nan=False).encode() if data is not None else None,headers=headers,method=method)
  try:
   with urllib.request.urlopen(req,timeout=20) as r:
    b=r.read();return json.loads(b) if b else None
  except (urllib.error.URLError,TimeoutError) as e:
   # Do not expose URLs, SQL errors or credentials in API responses.
   print('Supabase request failed:',type(e).__name__)
   raise DatabaseError('Database request failed. Check Supabase project status, SQL setup and server environment variables.') from None
 def rpc(self,name,args=None):return self.request('rpc/'+name,'POST',args or {})

"""Validation and real scikit-learn analytics retained from EarthScape."""
import math
from datetime import datetime,timezone
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
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

def analyze(rows,stations):
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
 return result

START=time.time()
def now():return datetime.now(timezone.utc).isoformat()
def pw_hash(p,s):return hashlib.pbkdf2_hmac('sha256',p.encode(),s.encode(),310000).hex()
def query(**kw):return '&'.join(quote(k,safe='')+'='+quote(str(v),safe='') for k,v in kw.items())
def cipher():
 key=os.environ.get('EARTHSCAPE_ENCRYPTION_KEY','')
 try:return Fernet(key.encode())
 except (ValueError,TypeError):raise DatabaseError('Set a valid EARTHSCAPE_ENCRYPTION_KEY in Vercel.') from None
def audit(db,actor,action):db.request('es_audit','POST',{'created':now(),'actor':actor,'action':action})
def bootstrap(db):
 # Insert missing demo accounts only. Deployment never resets existing passwords.
 if db.request('es_users?select=name&limit=1'):return
 users=[]
 for name in ['admin','analyst','viewer']:
  password=os.environ.get('EARTHSCAPE_'+name.upper()+'_PASSWORD','')
  if len(password)<12:raise DatabaseError('Set all three EARTHSCAPE account password variables to at least 12 characters, then redeploy.')
  salt=secrets.token_hex(16);users.append({'name':name,'salt':salt,'hash':pw_hash(password,salt),'role':name})
 db.request('es_users?on_conflict=name','POST',users,'resolution=ignore-duplicates')
def session(db,headers):
 try:c=SimpleCookie();c.load(headers.get('Cookie',''));token=c['sid'].value
 except (KeyError,ValueError):return None
 hashed=hashlib.sha256(token.encode()).hexdigest()
 rows=db.request('es_sessions?'+query(token_hash='eq.'+hashed,expires='gt.'+str(time.time()),select='name,csrf,token_hash',limit=1))
 if not rows:return None
 u=rows[0];roles=db.request('es_users?'+query(name='eq.'+u['name'],select='role',limit=1))
 if not roles:return None
 return dict(u,role=roles[0]['role'])
def ingest(db,rows,actor):
 if not isinstance(rows,list) or len(rows)>1000:raise ValueError('Import at most 1,000 records per request.')
 good=[];rejected=[]
 for i,r in enumerate(rows):
  try:good.append(dict(zip(['day','station','temperature','rainfall','co2','source','timestamp'],validate(r))))
  except (ValueError,TypeError,KeyError,OverflowError):rejected.append({'row':i+1,'error':'Invalid date, source, station or measurement.'})
 result=db.rpc('es_ingest',{'p_rows':good,'p_actor':actor});result['rejected']=rejected;return result
class handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send_json(self,status,data,cookie=None):
  raw=json.dumps(data,allow_nan=False).encode();self.send_response(status)
  for k,v in [('Content-Type','application/json'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]:self.send_header(k,v)
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(raw)
 def do_GET(self):self.handle_api('GET')
 def do_POST(self):self.handle_api('POST')
 def handle_api(self,method):
  try:
   result=self.dispatch(method)
   if result is not None:self.send_json(200,result)
  except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:self.send_json(400,{'error':str(e)[:180]})
  except DatabaseError as e:self.send_json(503,{'error':str(e)})
  except Exception as e:print('API error:',type(e).__name__);self.send_json(500,{'error':'Operation failed. Check Vercel function logs.'})
 def dispatch(self,method):
  parsed=urlparse(self.path);path=parsed.path
  endpoint=parse_qs(parsed.query).get('endpoint',[''])[0]
  if endpoint:path='/api/'+endpoint.strip('/')
  if path=='/api/health':return {'ok':True,'edition':'Vercel + Supabase','processing':'request-based monthly aggregation'}
  db=Database()
  if method=='POST':
   n=int(self.headers.get('Content-Length','0'))
   if n<0 or n>2_000_000:self.send_json(413,{'error':'Maximum request size is 2 MB.'});return
   body=json.loads(self.rfile.read(n) or b'{}')
   if not isinstance(body,dict):raise ValueError('Expected a JSON object.')
   if path=='/api/login':
    bootstrap(db)
    ip=self.headers.get('x-real-ip') or self.client_address[0]
    allowed=db.rpc('es_login_gate',{'p_key':hashlib.sha256(ip.encode()).hexdigest()})
    if not allowed:self.send_json(429,{'error':'Too many login attempts. Try again in five minutes.'});return
    rows=db.request('es_users?'+query(name='eq.'+str(body.get('name','')),limit=1))
    # A dummy hash keeps nonexistent usernames on the same password-hash path.
    r=rows[0] if rows else {'salt':'0'*32,'hash':'0'*64}
    valid=hmac.compare_digest(pw_hash(str(body.get('password','')),r['salt']),r['hash'])
    if not rows or not valid:self.send_json(401,{'error':'Invalid credentials'});return
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
    db.request('es_sessions?'+query(expires='lt.'+str(time.time())),'DELETE')
    db.request('es_sessions','POST',{'token_hash':hashlib.sha256(token.encode()).hexdigest(),'name':r['name'],'csrf':csrf,'expires':time.time()+3600})
    audit(db,r['name'],'Login')
    self.send_json(200,{'role':r['role']},'sid='+token+'; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=3600');return
  u=session(db,self.headers)
  if not u:self.send_json(401,{'error':'Please sign in'});return
  if method=='GET':
   if path=='/api/me':return {k:u[k] for k in ['name','role','csrf']}
   if path=='/api/analytics':
    station=parse_qs(parsed.query).get('station',[''])[0];rows=db.rpc('es_observations');stations=sorted({r['station'] for r in rows});selected=[r for r in rows if not station or r['station']==station];return analyze(selected,stations)
   if path=='/api/status':return db.rpc('es_status')
   if path=='/api/pipeline':return {'mode':'serverless','queued':0,'last_sync':None,'last_error':None}
   if path in ['/api/alerts','/api/jobs','/api/assets','/api/tickets','/api/audit','/api/users']:
    table=path.rsplit('/',1)[-1]
    if table in ['audit','users'] and u['role']!='admin':self.send_json(403,{'error':'Administrator required'});return
    selection='created,name,kind,id' if table=='assets' else 'name,role' if table=='users' else 'id,created,status,output,error' if table=='jobs' else '*'
    params={'select':selection,'limit':200,'order':'name.asc' if table=='users' else 'id.desc'}
    if table=='tickets' and u['role']!='admin':params['owner']='eq.'+u['name']
    return db.request('es_'+table+'?'+query(**params))
  else:
   if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),u['csrf']):self.send_json(403,{'error':'Invalid CSRF token'});return
   if path=='/api/logout':
    db.request('es_sessions?'+query(token_hash='eq.'+u['token_hash']),'DELETE');self.send_json(200,{},'sid=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Strict');return
   if path in ['/api/settings','/api/backup','/api/ticket-status','/api/user'] and u['role']!='admin':self.send_json(403,{'error':'Administrator required'});return
   if path in ['/api/ingest','/api/asset','/api/ack','/api/process'] and u['role']=='viewer':self.send_json(403,{'error':'Analyst or administrator required'});return
   if path=='/api/ingest':return ingest(db,list(csv.DictReader(io.StringIO(body['csv']))) if 'csv' in body else body['rows'],u['name'])
   if path=='/api/process':return db.rpc('es_process',{'p_actor':u['name']})
   if path=='/api/settings':
    threshold=float(body['threshold'])
    if not math.isfinite(threshold) or not -100<=threshold<=70:raise ValueError('Threshold must be between -100 and 70 C.')
    db.request('es_settings?key=eq.threshold','PATCH',{'value':str(threshold)});audit(db,u['name'],'Threshold updated');return {'threshold':threshold}
   if path=='/api/ack':db.request('es_alerts?'+query(id='eq.'+str(int(body['id']))),'PATCH',{'ack':1});return {'ok':True}
   if path=='/api/ticket':
    subject=str(body['subject']).strip();message=str(body['body']).strip()
    if not subject or not message or len(subject)>120 or len(message)>5000:raise ValueError('Subject and message required (120/5000 character limits).')
    return db.rpc('es_ticket',{'p_owner':u['name'],'p_subject':subject,'p_body':message})
   if path=='/api/ticket-status':
    if body['status'] not in ['Open','Resolved']:raise ValueError('Invalid status')
    db.request('es_tickets?'+query(id='eq.'+str(int(body['id']))),'PATCH',{'status':body['status']});return {'ok':True}
   if path=='/api/user':
    name=str(body['name']).strip();password=str(body['password']);role=body['role']
    if not name or len(name)>50 or role not in ['admin','analyst','viewer'] or not 12<=len(password)<=200:raise ValueError('Name, role and password of 12–200 characters required.')
    salt=secrets.token_hex(16);return db.rpc('es_save_user',{'p_name':name,'p_salt':salt,'p_hash':pw_hash(password,salt),'p_role':role,'p_actor':u['name']})
   if path=='/api/asset':
    raw=base64.b64decode(body['data'],validate=True)
    if len(raw)>1_000_000:raise ValueError('Images must be at most 1 MB.')
    if not raw.startswith((b'\x89PNG\r\n\x1a\n',b'II*\x00',b'MM\x00*')):raise ValueError('Only PNG/TIFF accepted.')
    with Image.open(io.BytesIO(raw)) as im:
     if im.width*im.height>20_000_000:raise ValueError('Image dimensions are too large.')
     im.verify()
    return db.rpc('es_asset',{'p_name':Path(str(body['name'])).name[:150],'p_payload':cipher().encrypt(raw).decode()})
   if path=='/api/backup':
    snapshot=db.rpc('es_snapshot');encrypted=cipher().encrypt(json.dumps(snapshot).encode()).decode();name=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)+'.json.enc'
    db.rpc('es_backup',{'p_name':name,'p_payload':encrypted});audit(db,u['name'],'Encrypted logical snapshot created');return {'file':name}
  self.send_json(404,{'error':'Not found'});return None
