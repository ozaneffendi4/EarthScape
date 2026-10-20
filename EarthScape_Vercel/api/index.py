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
