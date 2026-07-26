#!/usr/bin/env python3
"""Anneal the 10 controller port columns; objective = scored box of the whole grid."""
import sys, os, random, json, math
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,HERE)
from llm_eval import evaluate, PORTS

BAND=46            # hardware band rows added below the controller
SEEDS=[
 {'ri':55,'sp':65,'rp':75,'sc':95,'rr':119,'sd':125,'sa':163,'ss':225,'cc':245,'cr':275},
 {'ri':141,'sp':293,'rp':245,'sc':200,'rr':183,'sd':48,'sa':49,'ss':316,'cc':297,'cr':354},
 {'ri':121,'sp':282,'rp':248,'sc':163,'rr':128,'sd':48,'sa':48,'ss':400,'cc':290,'cr':361},
 {'ri':58,'sp':454,'rp':545,'sc':340,'rr':91,'sd':48,'sa':132,'ss':48,'cc':559,'cr':627},
 {'ri':51,'sp':211,'rp':156,'sc':172,'rr':139,'sd':316,'sa':255,'ss':307,'cc':268,'cr':399},
]
BASE=SEEDS[0]
LO=48

def box(cols, maxcol):
    r=evaluate(cols)
    if 'error' in r: return None,r
    h=r['height']+BAND
    w=max(r['width'], 321-277+r['width'])   # hardware overhang tracks controller width
    return max(w,h)**2, r

def main(seed, iters, maxcol):
    rng=random.Random(seed)
    cur=dict(SEEDS[seed%len(SEEDS)]) if seed<10 else {p:rng.randint(LO,maxcol) for p in PORTS}
    cur={p:min(maxcol,max(LO,v)) for p,v in cur.items()}
    c,r=box(cur,maxcol)
    while c is None:
        cur={p:rng.randint(LO,maxcol) for p in PORTS}; c,r=box(cur,maxcol)
    best=(c,dict(cur),r)
    T0=0.06
    for it in range(iters):
        T=T0*(1-it/iters)+1e-4
        cand=dict(cur)
        for _ in range(rng.choice([1,1,1,2,3])):
            p=rng.choice(PORTS)
            if rng.random()<0.6:
                cand[p]=max(LO,min(maxcol,cand[p]+rng.choice([-40,-16,-7,-3,-1,1,3,7,16,40])))
            else:
                cand[p]=rng.randint(LO,maxcol)
        c2,r2=box(cand,maxcol)
        if c2 is None: continue
        if c2<=c or rng.random()<math.exp(-(c2-c)/max(1.0,c*T)):
            cur,c=cand,c2
            if c2<best[0]: best=(c2,dict(cand),r2)
    print(json.dumps({'seed':seed,'maxcol':maxcol,'box':best[0],'cols':best[1],'r':best[2]}))

if __name__=='__main__':
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
