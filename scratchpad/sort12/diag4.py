#!/usr/bin/env python3
"""Ignore ALL semantic constraints: can four pipes be routed at all in the box,
and how long can the return pipe get?  Separates geometry from op-placement."""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import search as S
import drive

c = Counter()
best = 0
bestrooms = None


def probe(plan):
    global best, bestrooms
    msrc = plan.srcs('main')
    mdst = plan.dsts('main')
    for (rs, rsd) in msrc:
        for (rld, rldd) in plan.dsts('relay'):
            if rld == rs:
                continue
            for p2 in S.route(plan, rs, rsd, rld, rldd, set(), 2, 8, want=3, budget=15000):
                u2 = set(p2[0])
                c['p2'] += 1
                for (os_, osd) in msrc:
                    if os_ in u2:
                        continue
                    for (od, odd) in plan.dsts('outp'):
                        if od in u2 or od == os_:
                            continue
                        for p3 in S.route(plan, os_, osd, od, odd, u2, 2, 8, want=2,
                                          budget=15000):
                            u3 = u2 | set(p3[0])
                            c['p3'] += 1
                            for (idst, idd) in mdst:
                                if idst in u3:
                                    continue
                                for (isr, isd) in plan.srcs('inp'):
                                    if isr in u3 or isr == idst:
                                        continue
                                    for p4 in S.route(plan, isr, isd, idst, idd, u3, 2,
                                                      20, want=1, budget=15000):
                                        u4 = u3 | set(p4[0])
                                        c['p4'] += 1
                                        for (rd, rdd) in mdst:
                                            if rd in u4:
                                                continue
                                            for (rls, rlsd) in plan.srcs('relay'):
                                                if rls in u4 or rls == rd:
                                                    continue
                                                b = S.route_long(plan, rls, rlsd, rd,
                                                                 rdd, u4, 2, 30,
                                                                 budget=60000)
                                                if b:
                                                    c['ALL4'] += 1
                                                    if len(b[0]) > best:
                                                        best = len(b[0])
                                                        bestrooms = dict(plan.rooms)
                                                        print('ret', best, bestrooms,
                                                              flush=True)
                                                    return


def main():
    seen = set()
    for i, (mgrid, arole, rooms) in enumerate(drive.plans()):
        key = tuple(sorted(rooms.items()))
        if key in seen:
            continue
        seen.add(key)
        plan = S.Plan(rooms)
        if len(plan.free) < 21:
            continue
        c['plans'] += 1
        probe(plan)
    print('FINAL', dict(c), 'best return', best)


if __name__ == '__main__':
    main()
