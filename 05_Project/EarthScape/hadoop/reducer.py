#!/usr/bin/env python3
import sys
key=None;total=0.;count=0
for line in sys.stdin:
 k,v=line.rstrip().split('\t');v=float(v)
 if key is not None and k!=key:
  print(f'{key}\t{total/count:.4f}\t{count}');total=0.;count=0
 key=k;total+=v;count+=1
if count:print(f'{key}\t{total/count:.4f}\t{count}')
