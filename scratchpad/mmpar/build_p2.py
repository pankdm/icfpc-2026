#!/usr/bin/env python3
"""build_p2 -- matmul with TWO MAC engines (P=2), split by rows of C.

  SPL --[A queue]--> ADMX --> AREL1 -> MUL1 -> ACC1 <-> CREL1 -> MRG.O1
                          `-> AREL2 -> MUL2 -> ACC2 <-> CREL2 -> MRG.O2
  SPL --SD--> BDUP --> BREL1 --[B ring 1]--> MUL1 --> BREL1
                   `-> BREL2 --[B ring 2]--> MUL2 --> BREL2
  ADMX -S-> MCTLA, MCTLC, PCNT1, PCNT2, AREL1, AREL2   (the N,M,K broadcast)
  MCTLA -> ADMX.MA   (+M,-M,... N times, then 0 iff N odd -> phantom zero block)
  MCTLC -> MRG.MC    (+K,-K,... N times)

WHY THE FAN-OUT SITS ON ADMX AND EACH ENGINE HAS ITS OWN B RING: pipes cannot
cross, so the netlist must be PLANAR.  With SPL feeding BREL/PCNT/MCTLs and one
B ring chained MUL1->MUL2, the reduced graph contains K(3,3)
({SPL,engine1,engine2} x {ADMX,BREL,MRG}) and is provably unroutable -- the
PathFinder router confirmed it, stalling at ~700 permanently contended cells.
Moving the broadcast to ADMX and splitting the B ring makes it K(2,3) plus three
face-local edges, which is planar.

Geometry is deliberately sprawling; this is a correctness proof.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, HERE)
from mm2lib import Grid, pipe                        # noqa: E402
from mm2route import snake, pts_expand               # noqa: E402
import mm2rooms as R                                 # noqa: E402
import prooms as P                                   # noqa: E402
import router2                                       # noqa: E402

LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')
BOUND = (-340, -210, 420, 200)

POS = dict(
    I=(-300, -24), SPL=(-300, -8), BDUP=(-260, -6), ADMX=(-150, -8),
    MCTLA=(-150, 30), MCTLC=(-110, -4), MRG=(350, -8), O=(390, -1),
    AREL1=(-60, -110), MUL1=(-10, -110), BREL1=(-10, -150),
    ACC1=(60, -115), CREL1=(60, -90), PCNT1=(110, -90),
    AREL2=(-60, 102), MUL2=(-10, 102), BREL2=(-10, 142),
    ACC2=(60, 97), CREL2=(60, 122), PCNT2=(110, 122),
)
SIZE = dict(I=(3, 3), SPL=(16, 10), BDUP=(7, 4), ADMX=(17, 15),
            MCTLA=(11, 7), MCTLC=(11, 7), MRG=(17, 15), O=(3, 3),
            AREL1=(10, 9), MUL1=(8, 4), BREL1=(14, 10),
            ACC1=(16, 16), CREL1=(6, 4), PCNT1=(13, 10),
            AREL2=(10, 9), MUL2=(8, 4), BREL2=(14, 10),
            ACC2=(16, 16), CREL2=(6, 4), PCNT2=(13, 10))

APR = (-230, -25, 34, 9)        # A queue serpentine  (306 cells, tail at right)
BR1 = (-70, -175, 34, 9)        # engine 1 B ring
BR2 = (-70, 167, 34, 9)         # engine 2 B ring


def build(verbose=False):
    g = Grid()
    rm = {}
    for k in ('I', 'O'):
        g.room(*POS[k], 3, 3)
    g.put(POS['I'][0] + 1, POS['I'][1] + 1, 'I')
    g.put(POS['O'][0] + 1, POS['O'][1] + 1, 'O')
    rm['SPL'] = R.spl(g, *POS['SPL'])
    rm['BDUP'] = P.bdup(g, *POS['BDUP'])
    rm['ADMX'] = P.admx(g, POS['ADMX'][0], POS['ADMX'][1],
                        bcast=('BMA', 'BMC', 'BP1', 'BP2'))
    rm['MCTLA'] = P.mctl(g, POS['MCTLA'][0], POS['MCTLA'][1], 'M', True)
    rm['MCTLC'] = P.mctl(g, POS['MCTLC'][0], POS['MCTLC'][1], 'K', False)
    rm['MRG'] = P.mrg(g, *POS['MRG'])
    for n in ('1', '2'):
        a = rm['AREL' + n] = R.arel(g, *POS['AREL' + n])
        a.attach('AP', 'L', POS['AREL' + n][1] + 4, 'in')
        m = rm['MUL' + n] = R.mul(g, *POS['MUL' + n])
        m.attach('BF', 'T', POS['MUL' + n][0] + 1, 'out')
        mo, my = POS['MUL' + n]
        m.check({(mo + 4, my + 1): ('PP', 'out'), (mo + 3, my + 2): ('BF', 'out'),
                 (mo + 5, my + 1): ('AR', 'in'), (mo + 4, my + 2): ('BR', 'in')})
        rm['BREL' + n] = R.brel(g, *POS['BREL' + n])
        rm['ACC' + n] = R.acc(g, *POS['ACC' + n])
        rm['CREL' + n] = R.crel(g, *POS['CREL' + n])
        rm['PCNT' + n] = R.pcnt(g, *POS['PCNT' + n])

    A = lambda n, p: (rm[n].pipes[p][0], rm[n].pipes[p][1])

    snakes = {}
    for name, rect in (('AP', APR), ('B1', BR1), ('B2', BR2)):
        pts = snake(*rect)
        cells = pts_expand(pts)
        pipe(g, pts)
        snakes[name] = (cells, cells[0], cells[-1])
    apc, aph, apt = snakes['AP']
    b1c, b1h, b1t = snakes['B1']
    b2c, b2h, b2t = snakes['B2']

    nets = [
        ((POS['I'][0] + 1, POS['I'][1] + 3), 'S', A('SPL', 'IN'), 'S'),
        (A('SPL', 'AP'), 'W', aph, 'E'),
        (apt, 'E', A('ADMX', 'AP'), 'E'),
        (A('SPL', 'SD'), 'E', A('BDUP', 'BI'), 'E'),
        (A('BDUP', 'BO1'), 'N', A('BREL1', 'SD'), 'E'),
        (A('BDUP', 'BO2'), 'S', A('BREL2', 'SD'), 'E'),
        (A('ADMX', 'BMA'), 'S', A('MCTLA', 'MI'), 'E'),
        (A('ADMX', 'BMC'), 'E', A('MCTLC', 'MI'), 'E'),
        (A('ADMX', 'BP1'), 'E', A('PCNT1', 'CP'), 'E'),
        (A('ADMX', 'BP2'), 'E', A('PCNT2', 'CP'), 'E'),
        (A('MCTLA', 'MO'), 'E', A('ADMX', 'MA'), 'E'),
        (A('MCTLC', 'MO'), 'E', A('MRG', 'MC'), 'N'),
        (A('ADMX', 'AO1'), 'N', A('AREL1', 'AP'), 'E'),
        (A('ADMX', 'AO2'), 'S', A('AREL2', 'AP'), 'E'),
        (A('MRG', 'OUT'), 'E', (POS['O'][0] - 1, POS['O'][1] + 1), 'E'),
    ]
    for n, hd, tl in (('1', b1h, b1t), ('2', b2h, b2t)):
        nets += [
            (A('AREL' + n, 'AR'), 'E', A('MUL' + n, 'AR'), 'S'),
            (A('BREL' + n, 'BR'), 'S', hd, 'E'),
            (tl, 'E', A('MUL' + n, 'BR'), 'N'),
            (A('MUL' + n, 'BF'), 'N', A('BREL' + n, 'BF'), 'N'),
            (A('MUL' + n, 'PP'), 'E', A('ACC' + n, 'PP'), 'W'),
            (A('ACC' + n, 'CF'), 'W', A('CREL' + n, 'CF'), 'S'),
            (A('CREL' + n, 'CR'), 'S', A('ACC' + n, 'CR'), 'E'),
            (A('PCNT' + n, 'CTL'), 'S', A('ACC' + n, 'CTL'), 'N'),
            (A('ACC' + n, 'OUT'), 'E', A('MRG', 'O' + n),
             'S' if n == '1' else 'E'),
        ]
    rects = [(POS[k][0], POS[k][1], SIZE[k][0], SIZE[k][1]) for k in POS]
    router2.pathfinder(g, rects, nets, BOUND, prewired=[apc, b1c, b2c],
                       verbose=verbose,
                       iters=int(os.environ.get('ITERS', '60')))
    return g


def expect(n, m, k, a, b):
    return " ".join(str(sum(a[i * m + t] * b[t * k + j] for t in range(m)))
                    for i in range(n) for j in range(k))


def case(n, m, k, a, b):
    return (f"{n}x{m}x{k}", " ".join(map(str, [n, m, k] + a + b)),
            expect(n, m, k, a, b))


CASES = [
    case(2, 2, 2, [1, 2, 3, 4], [5, 6, 7, 8]),
    case(1, 1, 1, [7], [6]),
    case(1, 3, 2, [1, 2, 3], [1, 2, 3, 4, 5, 6]),
    case(3, 2, 1, [1, 2, 3, 4, 5, 6], [1, 2]),
    case(2, 1, 3, [2, 3], [1, 2, 3]),
    case(3, 3, 3, list(range(1, 10)), [1, 0, 0, 0, 1, 0, 0, 0, 1]),
    case(5, 2, 3, list(range(1, 11)), list(range(1, 7))),
    case(4, 3, 2, [-1, 2, -3, 4, -5, 6, 7, -8, 9, -10, 11, -12],
         [1, -2, 3, -4, 5, -6]),
]

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    g = build(verbose='-v' in sys.argv)
    txt = g.render()
    w, h, box = g.footprint()
    path = args[0] if args else '/tmp/mmpar_p2.man'
    open(path, 'w').write(txt + "\n")
    print(f"footprint {w}x{h} box={box} -> {path}")
    for name, inp, exp in CASES:
        o = subprocess.run([LM, '--grade', path, f'--input={inp}',
                            f'--expected={exp}', '--cap=400000'],
                           capture_output=True, text=True)
        print(f"{name:10s} {(o.stdout.strip() or o.stderr.strip())[:220]}")
