#!/usr/bin/env python3
"""build_p4 — matmul P=2: two whole engines, a splitter front-end, a merger.

  I -> BC --A--> ADMX --> FE1 -> ENGINE1 -> MRG.O1
          `-B--> BDUP -/  `--> FE2 -> ENGINE2 -> MRG.O2
  ADMX -S-> MCTLA (its own demux control) and MCTLC (MRG's control)
  MCTLA -> ADMX.MA   (+M,-M,... N times, then 0 -> phantom zero block)
  MCTLC -> MRG.MC    (+K,-K,... N times)

Engine i is an ORDINARY single-engine matmul (`build_e1.py`, 7/7 on the public
cases) solving a SMALLER problem: FE1 hands engine 1 the header (N1, M, K) with
N1 = ceil(N/2) and engine 1's half of A; FE2 hands engine 2 (N2, M, K) with
N2 = floor(N/2) + 1 -- the +1 is a phantom all-zero row, which keeps N2 >= 1 even
at N = 1 (a dense engine with N = 0 deadlocks on its first `r`).  ADMX emits that
phantom block last, so it is the last row engine 2 computes and MRG never reads
it.  Both engines get the whole of B, duplicated by BDUP.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, HERE)
from mm2lib import Grid                              # noqa: E402
import p3rooms as P3                                 # noqa: E402
import prooms as P                                   # noqa: E402
import router2                                       # noqa: E402
import build_e1 as E                                 # noqa: E402

LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')
EY = 700                                             # engine-2 y offset
BOUND = (-200, -320, 1000, 1250)

GPOS = dict(I=(330, 300), BC=(250, 420), ADMX=(250, 320), BDUP=(250, 520),
            MCTLA=(330, 340), MCTLC=(740, 700),
            FE1=(500, 290), FE2=(500, 540), MRG=(660, 700), O=(700, 708))
GSIZE = dict(I=(3, 3), BC=(17, 11), ADMX=(17, 15), BDUP=(8, 6),
             MCTLA=(11, 7), MCTLC=(11, 7), FE1=(22, 21), FE2=(22, 21),
             MRG=(17, 15), O=(3, 3))


def build(verbose=False):
    g = Grid()
    e1, in1, out1 = E.engine(g, 0, 0, io=False)
    e2, in2, out2 = E.engine(g, 0, EY, io=False)
    rm = {}
    for k in ('I', 'O'):
        g.room(*GPOS[k], 3, 3)
    g.put(GPOS['I'][0] + 1, GPOS['I'][1] + 1, 'I')
    g.put(GPOS['O'][0] + 1, GPOS['O'][1] + 1, 'O')
    rm['BC'] = P3.bcst(g, *GPOS['BC'])
    rm['ADMX'] = P3.admx3(g, *GPOS['ADMX'])
    rm['BDUP'] = P3.bdup2(g, *GPOS['BDUP'])
    rm['MCTLA'] = P3.mctl3(g, GPOS['MCTLA'][0], GPOS['MCTLA'][1], 'M', True,
                           side_in=('L', GPOS['MCTLA'][1] + 1),
                           side_out=('L', GPOS['MCTLA'][1] + 5))
    rm['MCTLC'] = P3.mctl3(g, GPOS['MCTLC'][0], GPOS['MCTLC'][1], 'K', False,
                           side_in=('T', GPOS['MCTLC'][0] + 7),
                           side_out=('T', GPOS['MCTLC'][0] + 3))
    rm['FE1'] = P3.fe(g, GPOS['FE1'][0], GPOS['FE1'][1], '1',
                      fo=('T', GPOS['FE1'][0] + 12))
    rm['FE2'] = P3.fe(g, GPOS['FE2'][0], GPOS['FE2'][1], '2',
                      fo=('B', GPOS['FE2'][0] + 12))
    rm['MRG'] = P.mrg(g, *GPOS['MRG'])
    A = lambda n, p: (rm[n].pipes[p][0], rm[n].pipes[p][1])

    nets = [
        ((GPOS['I'][0] + 1, GPOS['I'][1] + 3), 'S', A('BC', 'IN'), 'S'),
        (A('BC', 'OA'), 'N', A('ADMX', 'AP'), 'E'),
        (A('BC', 'OB'), 'S', A('BDUP', 'BI'), 'S'),
        (A('BC', 'OH1'), 'E', A('FE1', 'HI'), 'E'),
        (A('BC', 'OH2'), 'E', A('FE2', 'HI'), 'E'),
        (A('ADMX', 'MCA'), 'E', A('MCTLA', 'MI'), 'E'),
        (A('MCTLA', 'MO'), 'E', A('ADMX', 'MA'), 'W'),
        (A('ADMX', 'AO1'), 'N', A('FE1', 'DA'), 'E'),
        (A('ADMX', 'AO2'), 'S', A('FE2', 'DA'), 'E'),
        (A('BDUP', 'BO1'), 'W', A('FE1', 'DB'), 'E'),
        (A('BDUP', 'BO2'), 'S', A('FE2', 'DB'), 'E'),
        (A('MRG', 'OUT'), 'E', (GPOS['O'][0] - 1, GPOS['O'][1] + 1), 'E'),
        (A('ADMX', 'MCC'), 'E', A('MCTLC', 'MI'), 'S'),
        (A('MCTLC', 'MO'), 'N', A('MRG', 'MC'), 'N'),
    ]
    from mm2lib import pipe as _pipe
    from mm2route import pts_expand as _px
    hand = [
        ([A('FE1', 'FO'), (512, 240), (-85, 240), (-85, -139), in1], 'E'),
        ([A('FE2', 'FO'), (512, 565), (-70, 565), (-70, 552), (-85, 552),
          (-85, 561), in2], 'E'),
        ([out1, (214, 200), (620, 200), (620, 699), A('MRG', 'O1')], 'S'),
        ([out2, (214, 1000), (600, 1000), (600, 704), A('MRG', 'O2')], 'E'),
    ]
    hand_cells = []
    for pts, ed in hand:
        hand_cells += _px(pts)
        _pipe(g, pts, end_direction=ed)
    eng_cells = [c for c, ch in g.c.items() if ch != ' ']
    rects = [(GPOS[k][0], GPOS[k][1], GSIZE[k][0], GSIZE[k][1]) for k in GPOS]
    router2.pathfinder(g, rects, nets, BOUND, prewired=[eng_cells],
                       verbose=verbose,
                       iters=int(os.environ.get('ITERS', '40')))
    return g


def expect(n, m, k, a, b):
    return " ".join(str(sum(a[i * m + t] * b[t * k + j] for t in range(m)))
                    for i in range(n) for j in range(k))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    g = build(verbose='-v' in sys.argv)
    path = args[0] if args else '/tmp/mmpar_p4.man'
    open(path, 'w').write(g.render() + "\n")
    w, h, box = g.footprint()
    print(f"footprint {w}x{h} box={box} -> {path}")
    o = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'grade_fast.py'),
                        'matmul', path], capture_output=True, text=True)
    print((o.stdout.strip() or o.stderr.strip())[:400])
