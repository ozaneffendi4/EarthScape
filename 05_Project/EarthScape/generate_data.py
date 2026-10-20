import json,csv,random,math
from datetime import date,timedelta
from pathlib import Path
random.seed(42);rows=[]
for i in range(180):
 for station,base in [('Karachi',29),('Lahore',25),('Islamabad',21),('Quetta',17)]:
  rows.append(dict(day=(date(2026,1,1)+timedelta(days=i)).isoformat(),station=station,temperature=round(base+i*.025+math.sin(i/20)*4+random.gauss(0,1.2)+(15 if i in [52,123] else 0),2),rainfall=round(max(0,random.gauss(4,6)),2),co2=round(420+i*.025+random.gauss(0,2),2),source='weather' if i%2 else 'sensor'))
rows[5]['rainfall']=None;rows[20]['co2']=None
p=Path(__file__).parent/'data';p.mkdir(exist_ok=True)
(p/'sample.json').write_text(json.dumps(rows,indent=2))
with (p/'sample.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(p/'invalid.json').write_text(json.dumps([{'day':'bad','station':'X','temperature':22},{'day':'2026-10-01','station':'X','temperature':200}]))
