"""T2 topology (input->relay, main->relay, relay->main, main->output):
maximise total main<->relay buffering  Lr + Lm  over all 12x12 floorplans."""
import sys
from collections import Counter
sys.path.insert(0, 'scratchpad/sort12')
import search as S, drive
best=(0,None); c=Counter(); seen=set()
def collect(p,a,b,hi,cap=250):
    out=[]
    for (s,sd) in p.srcs(a):
        for (e,ed) in p.dsts(b):
            if s==e: continue
            for path in S.route(p,s,sd,e,ed,set(),2,hi,want=6,budget=10000):
                out.append((frozenset(path[0]), path))
                if len(out)>=cap: return out
    return out
for mgrid, arole, rooms in drive.plans():
    k=tuple(sorted(rooms.items()))
    if k in seen: continue
    seen.add(k)
    p=S.Plan(rooms)
    if len(p.free)<21: continue
    c['plans']+=1
    A=collect(p,'inp','relay',12)
    if not A: continue
    B=collect(p,'main','relay',20)
    if not B: continue
    C=collect(p,'main','outp',12)
    if not C: continue
    for a,_ in A:
        for b,pb in B:
            if a&b: continue
            for d,_ in C:
                if (a|b)&d: continue
                u=a|b|d
                for (rd,rdd) in p.dsts('main'):
                    if rd in u: continue
                    for (rls,rlsd) in p.srcs('relay'):
                        if rls in u: continue
                        bb=S.route_long(p,rls,rlsd,rd,rdd,u,2,30,budget=60000)
                        if bb:
                            tot=len(bb[0])
                            c['FOUR']+=1
                            if tot>best[0]:
                                best=(tot,dict(rooms),len(bb[0]),len(pb[0]))
                                print('LRONLY',tot,'Lr',len(bb[0]),'Lm',len(pb[0]),rooms,flush=True)
print('FINAL',dict(c),'best',best[0])
