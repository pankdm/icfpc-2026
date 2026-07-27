"""Sanity: the same 3-pipe + return-pipe test, but in a 13x13 box with main
pinned at (0,0)-(9,7).  If this finds solutions, the 12x12 zero is real."""
import os, sys
from collections import Counter
os.environ['SORTBOX'] = os.environ.get('SORTBOX', '13')
sys.path.insert(0, 'scratchpad/sort12')
import search as S
BOX = S.BOX
def places(w,h,occ):
    for y in range(BOX-h+1):
        for x in range(BOX-w+1):
            r=(x,y,x+w-1,y+h-1)
            if not (S.rect_cells(r)&occ): yield r
def collect(p,a,b,hi,cap=200):
    out=[]
    for (s,sd) in p.srcs(a):
        for (e,ed) in p.dsts(b):
            if s==e: continue
            for path in S.route(p,s,sd,e,ed,set(),2,hi,want=5,budget=10000):
                out.append(frozenset(path[0]))
                if len(out)>=cap: return out
    return out
c=Counter(); main=(0,0,9,7); mc=S.rect_cells(main)
for rrect in places(5,4,mc):
    rc=mc|S.rect_cells(rrect)
    for irect in places(3,3,rc):
        ic=rc|S.rect_cells(irect)
        for orect in places(3,3,ic):
            rooms={'main':main,'relay':rrect,'inp':irect,'outp':orect}
            p=S.Plan(rooms); c['plans']+=1
            A=collect(p,'inp','main',22)
            if not A: continue
            B=collect(p,'main','relay',12)
            if not B: continue
            C=collect(p,'main','outp',12)
            if not C: continue
            found=None
            for a in A:
                for b in B:
                    if a&b: continue
                    for d in C:
                        if (a|b)&d: continue
                        found=a|b|d; break
                    if found: break
                if found: break
            if not found: continue
            c['THREE']+=1
            got=False
            for (rd,rdd) in p.dsts('main'):
                if rd in found: continue
                for (rls,rlsd) in p.srcs('relay'):
                    if rls in found: continue
                    bb=S.route_long(p,rls,rlsd,rd,rdd,found,15,30,budget=40000)
                    if bb: got=True; break
                if got: break
            if got:
                c['FOUR']+=1
                if c['FOUR']<=2: print('OK', rooms, flush=True)
print('box',BOX,dict(c))
