#!/usr/bin/env python3
"""With all four pipes routed, how LONG can the return pipe be in a 12x12 box?

Routes the three short pipes first, then maximises the return pipe.  Prints the
best (return length, plan) found -- i.e. the real ceiling on buffering capacity.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mainroom
import search as S
import drive

best = (0, None)


def probe(plan, mgrid, asg):
    global best
    _, rs, rsd, os_, osd, rd, rdd, idst, idd = asg
    reserved = {rd, idst}
    for (rld, rldd) in plan.dsts('relay'):
        if rld in reserved or rld in (rs, os_):
            continue
        for p2 in S.route(plan, rs, rsd, rld, rldd, reserved | {os_}, 2, 8,
                          want=4, budget=20000):
            u2 = set(p2[0])
            for (od, odd) in plan.dsts('outp'):
                if od in u2 or od in reserved or od == os_:
                    continue
                for p3 in S.route(plan, os_, osd, od, odd, u2 | reserved, 2, 8,
                                  want=3, budget=20000):
                    u3 = u2 | set(p3[0])
                    for (isr, isd) in plan.srcs('inp'):
                        if isr in u3 or isr == rd:
                            continue
                        for p4 in S.route(plan, isr, isd, idst, idd, u3 | {rd}, 2, 20,
                                          want=2, budget=20000):
                            u4 = u3 | set(p4[0])
                            for (rls, rlsd) in plan.srcs('relay'):
                                if rls in u4 or rls == rd:
                                    continue
                                b = S.route_long(plan, rls, rlsd, rd, rdd, u4, 2, 30,
                                                 budget=120000)
                                if b and len(b[0]) > best[0]:
                                    best = (len(b[0]), dict(plan.rooms),
                                            [b, p2, p3, p4], mgrid, rldd)
                                    print('ret', best[0], plan.rooms, flush=True)


def main():
    for i, (mgrid, arole, rooms) in enumerate(drive.plans()):
        plan = S.Plan(rooms)
        if len(plan.free) < 21:
            continue
        for asg in drive.solve(mgrid, arole, rooms, 6):
            probe(plan, mgrid, asg)
    print('BEST return length', best[0])
    if best[1]:
        txt = S.render(S.Plan(best[1]), best[3], best[4], best[2])
        open(os.path.join(HERE, 'bestret.man'), 'w').write(txt or '')


if __name__ == '__main__':
    main()
