"""Run after starting app.py; exercises the supplied demonstration database."""
import urllib.request,urllib.error,http.cookiejar,json
from pathlib import Path
base='http://127.0.0.1:8080/api/'
def session(name,p):
 o=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def call(path,body=None,csrf=''):
  q=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-CSRF-Token':csrf})
  try:
   r=o.open(q);return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 assert call('login',{'name':name,'password':p})[0]==200
 return call,call('me')[1]['csrf']
results=[]
a,csrf=session('admin','EarthDemo!2026');assert a('settings',{'threshold':40})[0]==403;results.append('PASS missing CSRF rejected')
assert a('settings',{'threshold':40},csrf)[0]==200;results.append('PASS administrator setting update')
v,vc=session('viewer','ViewerDemo!2026')
for path,body in [('settings',{'threshold':20}),('backup',{}),('ingest',{'rows':[]}),('ack',{'id':1})]:
 assert v(path,body,vc)[0]==403;results.append('PASS viewer blocked: '+path)
assert v('analytics')[0]==200;results.append('PASS viewer analytics allowed')
assert v('ticket',{'subject':'Evaluation test','body':'Role access verified.'},vc)[0]==200;results.append('PASS viewer creates own support ticket')
assert a('backup',{},csrf)[0]==200;results.append('PASS encrypted backup API')
assert a('logout',{},csrf)[0]==200 and a('me')[0]==401;results.append('PASS logout invalidates session')
p=Path(__file__).resolve().parents[1]/'docs/integration-results.txt';p.write_text('\n'.join(results)+'\n');print('\n'.join(results))
