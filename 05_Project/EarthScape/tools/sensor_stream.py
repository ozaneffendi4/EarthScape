"""Authenticated sensor feeder; full timestamps preserve each reading."""
import urllib.request,http.cookiejar,json,time,os,random
jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));base=os.environ.get('EARTHSCAPE_URL','http://127.0.0.1:8080')
def req(path,data=None,csrf=''):
 r=urllib.request.Request(base+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','X-CSRF-Token':csrf});return json.load(client.open(r))
req('login',{'name':'analyst','password':os.environ['EARTHSCAPE_ANALYST_PASSWORD']});csrf=req('me')['csrf']
from datetime import datetime,timezone
for i in range(12):
 print(req('ingest',{'rows':[{'day':datetime.now(timezone.utc).isoformat(),'station':'LiveSensor-Karachi','temperature':round(random.uniform(25,45),1),'rainfall':0,'co2':425,'source':'sensor'}]},csrf));time.sleep(5)
