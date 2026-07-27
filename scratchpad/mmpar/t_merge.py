#!/usr/bin/env python3
"""Standalone proof of the ORDERED TWO-STREAM SPLIT+MERGE (blockers 1 and 3).

  I -> DIST -> {ADMX.AP, MCTLA.MI, MCTLC.MI}
  MCTLA -> ADMX.MA      (+Q,-Q,... N times, then 0 iff N odd)
  MCTLC -> MRG.MC       (+Q,-Q,... N times)
  ADMX -> AO1 -> EAT3_1 -> MRG.O1
  ADMX -> AO2 -> EAT3_2 -> MRG.O2
  MRG  -> O

Input  N Q Q v1 .. v(N*Q).   Correct output = v1..v(N*Q) IN ORDER.

The layout is a PLANAR embedding hand-routed with explicit waypoints: BFS
shortest paths (even with a 1-cell halo) wall the canvas off after 3-4 nets,
and no random ordering of 11 nets ever routed (400 tried).
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, HERE)
from mm2lib import Grid, pipe                        # noqa: E402
import prooms as P                                   # noqa: E402

LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')


def build():
    g = Grid()
    g.room(-10, 10, 3, 3)
    g.put(-9, 11, 'I')
    d = P.dist(g, 0, 10)
    ma = P.mctl(g, 30, 30, 'M', True)
    mc = P.mctl(g, 115, 45, 'K', False)
    ad = P.admx(g, 60, 10)
    e1 = P.eat3(g, 100, -8)
    e2 = P.eat3(g, 100, 32)
    mg = P.mrg(g, 140, 10)
    g.room(162, 18, 3, 3)
    g.put(163, 19, 'O')

    A = lambda r, n: (r.pipes[n][0], r.pipes[n][1])
    wires = [
        ([(-7, 11), A(d, 'IN')], 'E'),                                   # I -> DIST
        ([A(d, 'DD'), (45, 13), (45, 11), A(ad, 'AP')], 'E'),            # -> ADMX.AP
        ([A(d, 'DA'), (8, 31), A(ma, 'MI')], 'E'),                       # -> MCTLA
        ([A(d, 'DK'), (4, 60), (110, 60), (110, 46), A(mc, 'MI')], 'E'),  # -> MCTLC
        ([A(ma, 'MO'), (50, 33), (50, 23), A(ad, 'MA')], 'E'),           # MCTLA -> ADMX
        ([A(ad, 'AO1'), (71, -7), A(e1, 'EI')], 'E'),
        ([A(e1, 'EO'), (151, -5), A(mg, 'O1')], 'S'),
        ([A(ad, 'AO2'), (64, 33), A(e2, 'EI')], 'E'),
        ([A(e2, 'EO'), (135, 35), (135, 14), A(mg, 'O2')], 'E'),
        ([A(mc, 'MO'), (147, 48), A(mg, 'MC')], 'N'),
        ([A(mg, 'OUT'), (161, 19)], 'E'),
    ]
    for pts, ed in wires:
        pipe(g, pts, end_direction=ed)
    return g


def cases():
    out = []
    for n, q in ((3, 2), (1, 3), (4, 1), (5, 4), (2, 1), (1, 1), (7, 3), (6, 2)):
        vals = [10 * i + 1 for i in range(n * q)]
        out.append((f"N={n} Q={q}", f"{n} {q} {q} " + " ".join(map(str, vals)),
                    " ".join(map(str, vals))))
    return out


if __name__ == '__main__':
    g = build()
    path = '/tmp/mmpar_merge.man'
    open(path, 'w').write(g.render() + "\n")
    print("footprint", g.footprint())
    for name, inp, exp in cases():
        o = subprocess.run([LM, '--grade', path, f'--input={inp}',
                            f'--expected={exp}', '--cap=200000'],
                           capture_output=True, text=True)
        txt = (o.stdout.strip() or o.stderr.strip())[:300]
        print(f"{name:10s} {txt}")
