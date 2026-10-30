#!/usr/bin/env python3
"""clen.py orig_annot cand_annot...: per-chunk instruction counts (cand - orig), nonzero only, plus total."""
import sys,re,collections
def load(p):
    ch=[];cur=0;out=[];occ=collections.Counter()
    for l in open(p):
        if not l.strip(): continue
        a,rest=l.rstrip('\n').split(None,1)
        cur+=1
        if ' call ' in ' '+rest or rest.split(';')[0].strip()=='exit':
            lab=rest.split(';')[-1].strip()[:40] if ';' in rest else 'X'
            if rest.split(';')[0].strip()=='exit': lab='exit'
            occ[lab]+=1; out.append(((lab,occ[lab]),int(a,16)-0x22a10,cur)); cur=0
    return out
o=load(sys.argv[1]); cs=[dict((k,n) for k,a,n in load(p)) for p in sys.argv[2:]]
tot=[0]*len(cs)
for k,a,n in o:
    ds=[c.get(k,0)-n for c in cs]
    if any(ds): print(f'{a:#06x} {n:4d} {k[0][:38]:38s}#{k[1]:<2d}',' '.join(f'{d:+4d}' for d in ds))
