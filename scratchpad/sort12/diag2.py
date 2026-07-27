#!/usr/bin/env python3
"""Which pipe kills the 12x12 packing?  Counts assignments surviving each stage."""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mainroom
import search as S
import drive

c = Counter()


def probe(plan, mgrid, asg):
    _, rs, rsd, os_, osd, rd, rdd, idst, idd = asg
    cands = []
    for (rls, rlsd) in plan.srcs('relay'):
        if rls in (rs, os_, rd, idst):
            continue
        cands += S.route(plan, rls, rlsd, rd, rdd, {rs, os_, idst},
                         S.RET_MIN, S.RET_MIN + 5, want=200, budget=200000)
    if not cands:
        c['no_return'] += 1
        return
    c['return_ok'] += 1
    cands.sort(key=lambda p: len(p[0]))
    stage = 0
    for best in cands[:40]:
        used = set(best[0])
        for (rld, rldd) in plan.dsts('relay'):
            if rld in used or rld == os_ or rld == idst:
                continue
            p2 = S.route(plan, rs, rsd, rld, rldd, used | {os_, idst}, 2, 12, want=1)
            if not p2:
                continue
            stage = max(stage, 1)
            used2 = used | set(p2[0][0])
            for (od, odd) in plan.dsts('outp'):
                if od in used2 or od == idst:
                    continue
                p3 = S.route(plan, os_, osd, od, odd, used2 | {idst}, 2, 12, want=1)
                if not p3:
                    continue
                stage = max(stage, 2)
                used3 = used2 | set(p3[0][0])
                for (isr, isd) in plan.srcs('inp'):
                    if isr in used3:
                        continue
                    p4 = S.route(plan, isr, isd, idst, idd, used3, 2, 20, want=1)
                    if p4:
                        stage = max(stage, 3)
                        c['ALL4'] += 1
                        return
    c['stage%d' % stage] += 1


def main():
    for i, (mgrid, arole, rooms) in enumerate(drive.plans()):
        plan = S.Plan(rooms)
        if len(plan.free) < 21:
            continue
        asgs = drive.solve(mgrid, arole, rooms, 8)
        for asg in asgs:
            c['asg'] += 1
            probe(plan, mgrid, asg)
        if i % 500 == 0:
            print(i, dict(c), flush=True)
    print('FINAL', dict(c))


if __name__ == '__main__':
    main()
