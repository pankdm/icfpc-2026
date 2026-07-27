"""Geometric feasibility, input pipe routed FIRST (it is the most constrained)."""
import os, sys
from collections import Counter
sys.path.insert(0, 'scratchpad/sort12')
import search as S, drive
c = Counter(); seen=set(); best=0; bestr=None
def probe(p):
    global best, bestr
    for (isr, isd) in p.srcs('inp'):
        for (idst, idd) in p.dsts('main'):
            for p4 in S.route(p, isr, isd, idst, idd, set(), 2, 22, want=4, budget=40000):
                u1 = set(p4[0]); c['p_in'] += 1
                for (rs, rsd) in p.srcs('main'):
                    if rs in u1: continue
                    for (rld, rldd) in p.dsts('relay'):
                        if rld in u1: continue
                        for p2 in S.route(p, rs, rsd, rld, rldd, u1, 2, 8, want=2, budget=20000):
                            u2 = u1 | set(p2[0]); c['p_relay'] += 1
                            for (os_, osd) in p.srcs('main'):
                                if os_ in u2: continue
                                for (od, odd) in p.dsts('outp'):
                                    if od in u2: continue
                                    for p3 in S.route(p, os_, osd, od, odd, u2, 2, 8, want=2, budget=20000):
                                        u3 = u2 | set(p3[0]); c['p_out'] += 1
                                        for (rd, rdd) in p.dsts('main'):
                                            if rd in u3: continue
                                            for (rls, rlsd) in p.srcs('relay'):
                                                if rls in u3: continue
                                                b = S.route_long(p, rls, rlsd, rd, rdd, u3, 2, 30, budget=60000)
                                                if b:
                                                    c['ALL4'] += 1
                                                    if len(b[0]) > best:
                                                        best = len(b[0]); bestr = dict(p.rooms)
                                                        print('ret', best, bestr, flush=True)
                                                    return
for mgrid, arole, rooms in drive.plans():
    k = tuple(sorted(rooms.items()))
    if k in seen: continue
    seen.add(k)
    p = S.Plan(rooms)
    if len(p.free) < 21: continue
    c['plans'] += 1
    probe(p)
print('FINAL', dict(c), 'best return', best)
