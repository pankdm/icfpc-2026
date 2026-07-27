#!/usr/bin/env python3
"""Does a LONG p1 buy a SHORT p2?  (Decisive for every tighter geometry.)

belttrade.py showed p2>=99 passes at p1 = 5, 7 and 11, and that below 99 a
longer p1 lifts the pass count (p2=91: 0/7 at p1=5, 6/7 at p1=11).  That could
mean the invariant is total belt capacity with p2 merely correlated -- or that
p2 has its own floor.  The two differ by everything: p2>=99 makes 23x23
unroutable, total-capacity makes it easy, because the flush rule hands p1 the
whole MEM-flush lane (row 13, col 19) that p2 may never touch.

This build gives p1 the col-19 shaft (37 cells) and leaves p2 74 -- total 111,
MORE than the champion's 108, but p2 far under 99.

  python3 longp1.py
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

# p1 takes the col-19 shaft: it is flush against MEM's east wall, which is
# legal for p1 (MEM is its SOURCE) and permanently dead to p2.
P1 = [(14, 13), (14, 14), (18, 14), (18, 13), (19, 13), (19, 0),
      (20, 0), (20, 14), (20, 15)]
# p2 gives up cols 19/20 and snakes on 21/22 + the col-23 descent.
P2 = [(21, 15), (21, 14), (21, 0), (22, 0), (22, 13), (23, 13), (23, 23),
      (14, 23), (13, 23),
      (13, 22), (14, 22), (14, 21), (13, 21), (13, 20), (14, 20),
      (14, 19), (13, 19), (13, 18), (14, 18), (14, 17), (13, 17),
      (13, 16), (14, 16), (14, 15), (13, 15), (13, 14),
      (9, 14), (9, 13)]


def length(pts):
    n = 1
    for i in range(len(pts) - 1):
        n += abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
    return n


def build(p1, p2):
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
    out = os.path.join(HERE, 'longp1.man')
    prog = build(P1, P2)
    prog.save(out)
    print('p1=%d p2=%d total=%d  footprint=%s'
          % (length(P1), length(P2), length(P1) + length(P2), prog.footprint()))
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'grade_fast.py'),
                        'memory', out], capture_output=True, text=True)
    print(r.stdout.strip()[:400])


if __name__ == '__main__':
    main()
