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
