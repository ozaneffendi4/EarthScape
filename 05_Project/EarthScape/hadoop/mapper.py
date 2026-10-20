#!/usr/bin/env python3
import sys,json,math
for line in sys.stdin:
 try:
  r=json.loads(line);t=float(r['temperature'])
  if not math.isfinite(t):continue
  print(f"{r['station']}|{r['day'][:7]}\t{t}")
 except (ValueError,KeyError,TypeError):continue
