#!/usr/bin/env python3
"""Print one floorplan that has a >=15 return pipe, to see why the rest won't fit."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mainroom
import search as S
import drive

n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
shown = 0
for mgrid, arole, rooms in drive.plans():
    plan = S.Plan(rooms)
    if len(plan.free) < 21:
        continue
    for asg in drive.solve(mgrid, arole, rooms, 4):
        _, rs, rsd, os_, osd, rd, rdd, idst, idd = asg
        cands = []
        for (rls, rlsd) in plan.srcs('relay'):
            if rls in (rs, os_, rd, idst):
                continue
            cands += S.route(plan, rls, rlsd, rd, rdd, {rs, os_, idst},
                             S.RET_MIN, S.RET_MIN + 3, want=30, budget=80000)
        if not cands:
            continue
        shown += 1
        if shown < n:
            break
        g = [['.'] * S.BOX for _ in range(S.BOX)]
        for name, ch in (('main', 'M'), ('relay', 'L'), ('inp', 'I'), ('outp', 'O')):
            for (x, y) in S.rect_cells(rooms[name]):
                g[y][x] = ch
        cands.sort(key=lambda p: len(p[0]))
        for c in cands[0][0]:
            g[c[1]][c[0]] = '*'
        for lbl, c in (('R', rs), ('O', os_), ('r', rd), ('i', idst)):
            g[c[1]][c[0]] = lbl
        print('rooms', rooms)
        print('free', len(plan.free), 'ret', len(cands[0][0]))
        print('relay dsts', [c for c, d in plan.dsts('relay')])
        print('\n'.join(''.join(r) for r in g))
        sys.exit(0)
