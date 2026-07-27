"""Alternative pipe topologies in 12x12: which ones fit geometrically?
  T1  input->main, main->relay, relay->main, main->output     (current)
  T2  input->relay, main->relay, relay->main, main->output
  T3  input->relay, main->relay, relay->main, relay->output
Reports plans admitting all pipes, and with the return pipe >= 15."""
import sys
from collections import Counter
sys.path.insert(0, 'scratchpad/sort12')
import search as S, drive

TOPO = {
 'T1': [('inp','main',22), ('main','relay',12), ('main','outp',12)],
 'T2': [('inp','relay',12), ('main','relay',12), ('main','outp',12)],
 'T3': [('inp','relay',12), ('main','relay',12), ('relay','outp',12)],
}

def collect(p, a, b, hi, cap=300):
    out=[]
    for (s,sd) in p.srcs(a):
        for (e,ed) in p.dsts(b):
            if s==e: continue
            for path in S.route(p,s,sd,e,ed,set(),2,hi,want=5,budget=10000):
                out.append(frozenset(path[0]))
                if len(out)>=cap: return out
    return out

res={k:Counter() for k in TOPO}
seen=set()
for mgrid, arole, rooms in drive.plans():
    k=tuple(sorted(rooms.items()))
    if k in seen: continue
    seen.add(k)
    p=S.Plan(rooms)
    if len(p.free)<21: continue
    for name, spec in TOPO.items():
        c=res[name]; c['plans']+=1
        sets=[collect(p,a,b,hi) for a,b,hi in spec]
        if not all(sets): continue
        c['each_ok']+=1
        found=None
        for a in sets[0]:
            for b in sets[1]:
                if a&b: continue
                for d in sets[2]:
                    if (a|b)&d: continue
                    found=a|b|d; break
                if found: break
            if found: break
        if not found: continue
        c['THREE']+=1
        for (rd,rdd) in p.dsts('main'):
            if rd in found: continue
            for (rls,rlsd) in p.srcs('relay'):
                if rls in found: continue
                bb=S.route_long(p,rls,rlsd,rd,rdd,found,15,30,budget=50000)
                if bb:
                    c['FOUR']+=1
                    break
            if c['FOUR']: break
for name in TOPO:
    print(name, dict(res[name]), flush=True)
