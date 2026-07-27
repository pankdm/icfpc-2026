#!/usr/bin/env python3
"""Is the belt floor about p2's LENGTH or about TOTAL belt capacity?

rewind-incell passes with p1=5, p2=103 and fails at p2=98 (measured, bisected).
If the real invariant is p1+p2, then lengthening p1 by k must buy k cells off
p2.  This rebuilds rewind-incell with a longer p1 (a zigzag over the free
row-13/14 cells east of the tap, all of which are flush against MEM -- legal,
MEM is p1's SOURCE) and a p2 truncated by the same amount, and grades each.

  python3 belttrade.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'memory'))

import rewind_incell_build as base
from littleman import Program

# p1 variants, shortest first.  Every intermediate cell sits on row 13/14 east
# of the tap, flush under MEM; the source cell (14,13) still leaves the wall
# perpendicular, which is what the parser requires of an attachment.
P1_VARIANTS = {  # trimmed
    5:  [(14, 13), (14, 14), (16, 14), (16, 15)],
    7:  [(14, 13), (14, 14), (15, 14), (15, 13), (16, 13), (16, 14), (16, 15)],
    11: [(14, 13), (14, 14), (15, 14), (15, 13), (16, 13), (16, 14),
         (17, 14), (17, 13), (18, 13), (18, 14), (18, 15)],
    15: [(14, 13), (14, 14), (12, 14), (12, 13), (13, 13), (13, 14),
         (15, 14), (15, 13), (16, 13), (16, 14),
         (17, 14), (17, 13), (18, 13), (18, 14), (18, 15)],
}


def p2_of(d):
    """rewind-incell's p2 with the cols 20/21 hairpin cut short by d rows.

    The ATTACHMENT COLUMNS must not move: X_P2 is what puts the CMD/P2 binding
    midpoint at 6.5, and shortening p2 by walking its terminal east silently
    re-binds every `r` in the tap.  So the cells come off the middle of the
    snake instead, where nothing is bound."""
    pts = [(21, 15), (21, 14), (20, 14), (19, 14), (19, 13), (20, 13),
           (20, d), (21, d), (21, 13), (22, 13), (22, 0), (23, 0), (23, 23),
           (14, 23), (13, 23),
           (13, 22), (14, 22), (14, 21), (13, 21), (13, 20), (14, 20),
           (14, 19), (13, 19), (13, 18), (14, 18), (14, 17), (13, 17),
           (13, 16), (14, 16), (14, 15), (13, 15), (13, 14),
           (9, 14), (9, 13)]
    return pts, d


def length(pts):
    n = 1
    for i in range(len(pts) - 1):
        n += abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
    return n


def build(p1, p2):
    """base.build() draws pipes straight onto the grid, so swap them by
    intercepting Program.pipe: the 4th call is p1 and the 5th is p2."""
    orig = Program.pipe
    calls = {'n': 0}

    def patched(self, points, **kw):
        calls['n'] += 1
        if calls['n'] == 4:
            points = p1
        elif calls['n'] == 5:
            points = p2
        return orig(self, points, **kw)

    Program.pipe = patched
    try:
        return base.build()
    finally:
        Program.pipe = orig


def main():
    out = os.path.join(HERE, 'trade.man')
    for p1len, p1 in [(5, P1_VARIANTS[5])]:
        for d in (0, 1, 2):
            p2, _ = p2_of(d)
            prog = build(p1, p2)
            prog.save(out)
            r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'grade_fast.py'),
                                'memory', out], capture_output=True, text=True)
            txt = r.stdout.strip()
            if '"passed"' in txt:
                import json as _j
                v = _j.loads(txt)
                ok = f'passed={v["passed"]} avgTicks={v["avgTicks"]} score={v["score"]}'
            else:
                ok = 'ERR ' + (r.stderr or txt)[:100].replace('\n', ' ')
            print(f'p1={p1len:>3} p2={length(p2):>3} total={p1len + length(p2):>4}  {ok}', flush=True)


if __name__ == '__main__':
    main()
