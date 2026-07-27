"""How small must the main room be before 12x12 can carry all four pipes?
Sweeps main room (W,H); reports plans admitting 3 short pipes, and 4 with the
return pipe >= RET."""
import os, sys, itertools
from collections import Counter
sys.path.insert(0, 'scratchpad/sort12')
import search as S

BOX = S.BOX
def places(w, h, occ):
    for y in range(BOX-h+1):
        for x in range(BOX-w+1):
            r = (x, y, x+w-1, y+h-1)
            if not (S.rect_cells(r) & occ): yield r

def collect(p, kind, cap=300):
    if kind=='in': pairs=[(a,b) for a in p.srcs('inp') for b in p.dsts('main')]; hi=22
    elif kind=='rel': pairs=[(a,b) for a in p.srcs('main') for b in p.dsts('relay')]; hi=12
    else: pairs=[(a,b) for a in p.srcs('main') for b in p.dsts('outp')]; hi=12
    out=[]
    for (s,sd),(e,ed) in pairs:
        if s==e: continue
        for path in S.route(p,s,sd,e,ed,set(),2,hi,want=5,budget=10000):
            out.append(frozenset(path[0]))
            if len(out)>=cap: return out
    return out

RET = 15
for (mw, mh) in [(10,8),(9,8),(10,7),(9,7),(8,8),(10,6),(8,7)]:
    c = Counter(); seen=set()
    for mrect in places(mw, mh, set()):
        mc = S.rect_cells(mrect)
        for rshape in ((5,4),(4,5)):
            for rrect in places(rshape[0], rshape[1], mc):
                rc = mc | S.rect_cells(rrect)
                for irect in places(3,3,rc):
                    ic = rc | S.rect_cells(irect)
                    for orect in places(3,3,ic):
                        rooms={'main':mrect,'relay':rrect,'inp':irect,'outp':orect}
                        k=tuple(sorted(rooms.items()))
                        if k in seen: continue
                        seen.add(k)
                        p=S.Plan(rooms)
                        c['plans']+=1
                        A=collect(p,'in'); 
                        if not A: continue
                        B=collect(p,'rel')
                        if not B: continue
                        C=collect(p,'out')
                        if not C: continue
                        done=False
                        for a in A:
                            for b in B:
                                if a&b: continue
                                for d in C:
                                    if (a|b)&d: continue
                                    c['THREE']+=1
                                    u=a|b|d
                                    for (rd,rdd) in p.dsts('main'):
                                        if rd in u: continue
                                        for (rls,rlsd) in p.srcs('relay'):
                                            if rls in u: continue
                                            bb=S.route_long(p,rls,rlsd,rd,rdd,u,RET,30,budget=50000)
                                            if bb:
                                                c['FOUR']+=1; done=True; break
                                        if done: break
                                    done=True; break
                                if done: break
                            if done: break
    print(mw, mh, 'area', mw*mh, dict(c), flush=True)
