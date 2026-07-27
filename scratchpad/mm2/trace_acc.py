"""Print ACC's man route cell-by-cell from the unit-test rig.

The room is a maze of three racetracks joined by a merge node; the excursion cost
is a property of the ROUTE, not the glyph count, so compressing it safely needs
the actual walk order rather than a reading of the grid.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'scratchpad', 'mm2'))
LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')

import unit                                      # noqa: E402

# rebuild the ACC rig without running it
import mm2rooms as R                             # noqa: E402
from mm2lib import Grid, pipe                    # noqa: E402

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
OX, OY = 20, 20


def build():
    g = Grid()
    g.room(0, 0, 3, 3); g.put(1, 1, 'I')
    pc = R.pcnt(g, 0, 6)
    acc = R.acc(g, OX, OY)
    crel = R.crel(g, 10, 22)
    g.room(40, 30, 6, 4)
    g.text(41, 31, "@>5v")
    g.text(41, 32, " ^s<")
    g.room(38, 21, 3, 3); g.put(39, 22, 'O')
    P = lambda n: (pc.pipes[n][0], pc.pipes[n][1])
    Ac = lambda n: (acc.pipes[n][0], acc.pipes[n][1])
    C = lambda n: (crel.pipes[n][0], crel.pipes[n][1])
    pipe(g, [(1, 3), (1, 4), (-2, 4), (-2, P('CP')[1]), P('CP')], 'E')
    pipe(g, [P('CTL'), (P('CTL')[0], 38), (Ac('CTL')[0], 38), Ac('CTL')], 'N')
    pipe(g, [(39, 31), (38, 31), (38, Ac('PP')[1]), Ac('PP')], 'W')
    pipe(g, [Ac('CF'), (18, Ac('CF')[1]), (18, C('CF')[1]), C('CF')], 'S')
    pipe(g, [C('CR'), (C('CR')[0], 28), (19, 28), Ac('CR')], 'E')
    pipe(g, [Ac('OUT'), (37, Ac('OUT')[1])], 'E')
    return g


g = build()
txt = g.render()
path = '/tmp/mm2trace.man'
open(path, 'w').write(txt + '\n')
rows = txt.split('\n')


def gl(x, y):
    return rows[y][x] if 0 <= y < len(rows) and 0 <= x < len(rows[y]) else ' '


o = subprocess.run([LM, path, str(STEPS), '--input=2 2 2', '--expected=10 10 10 10'],
                   capture_output=True, text=True)
prev = None
for i, line in enumerate(o.stdout.strip().split('\n')):
    try:
        j = json.loads(line)
    except Exception:
        continue
    men = j.get('runners') or j.get('men') or []
    # the ACC man is the one inside the ACC box
    here = [(m['pos'][0], m['pos'][1], m.get('a'), m.get('b'), m.get('backpack'))
            for m in men
            if OX <= m['pos'][0] < OX + 16 and OY <= m['pos'][1] < OY + 16]
    if not here:
        continue
    x, y, a, b, bp = here[0]
    cur = (x, y)
    if cur != prev:
        print(f"t{i:4d} ({x - OX:2d},{y - OY:2d}) {gl(x, y)!r} A={a} B={b} BP={bp}")
    prev = cur
