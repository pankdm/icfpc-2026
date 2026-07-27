#!/usr/bin/env python3
"""Where does the 12x12 search die?  Counts plans surviving each filter."""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mainroom
import search as S
import drive


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    c = Counter()
    bestlen = 0
    for i, (mgrid, arole, rooms) in enumerate(drive.plans()):
        if i >= limit:
            break
        c['plans'] += 1
        plan = S.Plan(rooms)
        c['free>=21'] += len(plan.free) >= 21
        if len(plan.free) < 21:
            continue
        asgs = drive.solve(mgrid, arole, rooms, 5)
        if not asgs:
            continue
        c['attach_ok'] += 1
        # longest relay->main path over the assignments we kept
        got = 0
        for asg in asgs:
            _, rs, rsd, os_, osd, rd, rdd, idst, idd = asg
            for (rls, rlsd) in plan.srcs('relay'):
                if rls in (rs, os_, rd, idst):
                    continue
                b = S.route_long(plan, rls, rlsd, rd, rdd, {rs, os_, idst}, 2, 40,
                                 budget=60000)
                if b:
                    got = max(got, len(b[0]))
        if got:
            c['ret_any'] += 1
            bestlen = max(bestlen, got)
            if got >= 15:
                c['ret>=15'] += 1
        if c['plans'] % 20000 == 0:
            print(dict(c), 'bestret', bestlen, flush=True)
    print(dict(c), 'bestret', bestlen)


if __name__ == '__main__':
    main()
