#!/usr/bin/env python3
"""Anneal port columns under the constraints that keep _attach_tight routable.

Order is pinned to ri<sp<rp<sc<rr<sd<sa<ss<cc<cr (already within 1% of the
minimum-feedback-arc optimum for the op stream); only the SPACING moves, and the
spacings are exactly the clearances each service room and pipe leg needs.
"""
import sys, os, random, json, math
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,HERE)
from llm_eval import evaluate, PORTS

OPMIN=44          # x0 + ncorr + 2 with ncorr=42
ORDER=['ri','sp','rp','sc','rr','sd','sa','ss','cc','cr']

def repair(c):
    """Clamp to the routability constraints, keeping every gap satisfied."""
    c=dict(c)
    c['ri']=max(OPMIN,c['ri'])
    c['sp']=max(c['sp'], c['ri']+3)
    c['rp']=max(c['rp'], c['sp']+6)
    c['sc']=max(c['sc'], c['sp']+11, c['rp']+6)
    c['rr']=max(c['rr'], c['sc']+24)
    c['sd']=max(c['sd'], c['rr']+1)
    c['sa']=max(c['sa'], c['sd']+10, c['sc']+31)
    c['ss']=max(c['ss'], c['sa']+10)
    c['cc']=max(c['cc'], c['ss']+6, c['sc']+81)
    c['cr']=max(c['cr'], c['cc']+24)
    return c

def total(c):
    r=evaluate(c)
    if 'error' in r: return None,r
    height=r['height']+45
    width=max(c['cr']+2, c['cc']+76)
    return max(width,height)**2, dict(r, box_w=width, box_h=height)

BASE={'ri':55,'sp':65,'rp':75,'sc':95,'rr':119,'sd':125,'sa':163,'ss':225,'cc':245,'cr':275}

def main(seed, iters, span):
    rng=random.Random(seed)
    cur=repair(BASE if seed==0 else {p:BASE[p]+rng.randint(-30,span) for p in PORTS})
    c,r=total(cur)
    while c is None:
        cur=repair({p:BASE[p]+rng.randint(-30,span) for p in PORTS}); c,r=total(cur)
    best=(c,dict(cur),r)
    for it in range(iters):
        T=0.05*(1-it/iters)+1e-4
        cand=dict(cur)
        for _ in range(rng.choice([1,1,2,3])):
            p=rng.choice(PORTS)
            cand[p]=max(OPMIN,cand[p]+rng.choice([-60,-25,-10,-4,-1,1,4,10,25,60]))
        cand=repair(cand)
        c2,r2=total(cand)
        if c2 is None: continue
        if c2<=c or rng.random()<math.exp(-(c2-c)/max(1.0,c*T)):
            cur,c=cand,c2
            if c2<best[0]: best=(c2,dict(cand),r2)
    print(json.dumps({'seed':seed,'box':best[0],'cols':best[1],'r':best[2]}))

if __name__=='__main__':
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
