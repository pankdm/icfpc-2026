#!/usr/bin/env python3
"""build_e1 — a LOOSE single matmul engine whose I/O are ordinary pipes, so it
can be instantiated twice for P=2.

`build_dense`'s engine cannot be reused as a black box: with its I/O rooms
removed both ports are sealed inside the fold (flood fill reaches 30 free cells
from ACC.OUT and escapes for none of 48 DX/DY/PPX/CTLX variants, even with ZERO
clearance).  The seal is the PP corridor, which wraps ACC's north and east
because mm2rooms' default ports put PP and OUT on the same wall.

`scratchpad/mmpar/psolve.py` shows those defaults are only one of thousands of
nearest-pipe-legal choices.  This build picks a set that needs no wrap at all:

    SPL  IN=T@5  AP=R@2  SD=B@11  CP=T@14
    AREL AP=L@4  AR=B@5
    MUL  AR=T@1  BR=L@2  BF=B@2   PP=B@5        (PP leaves the SOUTH wall)
    BREL SD=T@1  BF=L@8  BR=B@1
    ACC  CR=T@1  PP=T@12 CF=B@1   CTL=B@3  OUT=B@14   (PP north, OUT south)
    CREL CF=L@1  CR=R@2
    PCNT CP=L@4  CTL=T@6

MUL sits due north of ACC so PP drops straight down; OUT leaves ACC's south wall
into open air.  Every wire is hand-routed on a crossing-free (planar) embedding —
box is irrelevant here, correctness is the gate.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, HERE)
from mm2lib import Grid, pipe                        # noqa: E402
from mm2route import snake                           # noqa: E402
import mm2rooms as R                                 # noqa: E402

LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')

POS = dict(I=(-140, -142), INREL=(-80, -140), SPL=(0, 0), AREL=(200, 0), MUL=(200, 80),
           BREL=(0, 80), ACC=(200, 160), CREL=(140, 160), PCNT=(240, -60),
           O=(250, 190))
APR = (30, -90, 34, 9)          # A queue serpentine  (306 cells)
BRR = (0, 110, 34, 9)           # B ring serpentine


def engine(g, ox=0, oy=0, io=True):
    """Stamp one engine at (ox,oy).  Returns (rooms, IN att, OUT att)."""
    P = {k: (v[0] + ox, v[1] + oy) for k, v in POS.items()}
    rm = {}
    rm['SPL'] = R.spl(g, *P['SPL'])
    rm['AREL'] = R.arel(g, *P['AREL'])
    rm['MUL'] = R.mul(g, *P['MUL'])
    rm['BREL'] = R.brel(g, *P['BREL'])
    rm['ACC'] = R.acc(g, *P['ACC'])
    rm['CREL'] = R.crel(g, *P['CREL'])
    rm['PCNT'] = R.pcnt(g, *P['PCNT'])
    rm['INREL'] = R.crel(g, *P['INREL'])
    rm['INREL'].attach('CF', 'L', P['INREL'][1] + 1, 'in')
    rm['INREL'].attach('CR', 'B', P['INREL'][0] + 3, 'out')

    def at(n, p, side, off, kind):
        rm[n].attach(p, side, off, kind)

    sx, sy = P['SPL']
    at('SPL', 'IN', 'T', sx + 5, 'in'); at('SPL', 'AP', 'R', sy + 2, 'out')
    at('SPL', 'SD', 'B', sx + 11, 'out'); at('SPL', 'CP', 'T', sx + 14, 'out')
    rm['SPL'].check({(sx + 4, sy + 3): ('AP', 'out'),
                     (sx + 13, sy + 6): ('SD', 'out')})
    ax, ay = P['AREL']
    at('AREL', 'AP', 'L', ay + 4, 'in'); at('AREL', 'AR', 'B', ax + 5, 'out')
    mx, my = P['MUL']
    at('MUL', 'AR', 'T', mx + 1, 'in'); at('MUL', 'BR', 'L', my + 2, 'in')
    at('MUL', 'BF', 'B', mx + 2, 'out'); at('MUL', 'PP', 'B', mx + 5, 'out')
    rm['MUL'].check({(mx + 4, my + 1): ('PP', 'out'), (mx + 3, my + 2): ('BF', 'out'),
                     (mx + 5, my + 1): ('AR', 'in'), (mx + 4, my + 2): ('BR', 'in')})
    bx, by = P['BREL']
    at('BREL', 'SD', 'T', bx + 1, 'in'); at('BREL', 'BF', 'L', by + 8, 'in')
    at('BREL', 'BR', 'B', bx + 1, 'out')
    rm['BREL'].check({(bx + 2, by + 1): ('SD', 'in'), (bx + 3, by + 1): ('SD', 'in'),
                      (bx + 5, by + 1): ('SD', 'in'), (bx + 4, by + 4): ('SD', 'in'),
                      (bx + 9, by + 7): ('BF', 'in')})
    cx, cy = P['ACC']
    at('ACC', 'CR', 'T', cx + 1, 'in'); at('ACC', 'PP', 'T', cx + 12, 'in')
    at('ACC', 'CF', 'B', cx + 1, 'out'); at('ACC', 'CTL', 'R', cy + 11, 'in')
    at('ACC', 'OUT', 'B', cx + 14, 'out')
    rm['ACC'].check({(cx + 6, cy + 2): ('CR', 'in'), (cx + 6, cy + 4): ('CR', 'in'),
                     (cx + 8, cy + 4): ('PP', 'in'), (cx + 13, cy + 5): ('PP', 'in'),
                     (cx + 3, cy + 12): ('CTL', 'in'), (cx + 3, cy + 13): ('CTL', 'in'),
                     (cx + 7, cy + 5): ('CF', 'out'), (cx + 6, cy + 3): ('CF', 'out'),
                     (cx + 7, cy + 7): ('CF', 'out'), (cx + 9, cy + 2): ('OUT', 'out')})
    rx, ry = P['CREL']
    at('CREL', 'CF', 'L', ry + 1, 'in'); at('CREL', 'CR', 'R', ry + 2, 'out')
    px, py = P['PCNT']
    at('PCNT', 'CP', 'T', px + 2, 'in'); at('PCNT', 'CTL', 'B', px + 6, 'out')

    A = lambda n, p: (rm[n].pipes[p][0], rm[n].pipes[p][1])
    o = lambda pts: [(x + ox, y + oy) for x, y in pts]
    apr = (APR[0] + ox, APR[1] + oy, APR[2], APR[3])
    brr = (BRR[0] + ox, BRR[1] + oy, BRR[2], BRR[3])

    wires = [
        ([A('SPL', 'AP')] + o([(20, 2), (20, -90)]) + snake(*apr) +
         o([(70, -82), (70, -70), (180, -70), (180, 4)]) + [A('AREL', 'AP')], 'E'),
        ([A('SPL', 'SD')] + o([(11, 40), (1, 40)]) + [A('BREL', 'SD')], 'S'),
        ([A('AREL', 'AR')] + o([(205, 40), (201, 40)]) + [A('MUL', 'AR')], 'S'),
        ([A('BREL', 'BR')] + o([(1, 105), (-5, 105), (-5, 110)]) + snake(*brr) +
         o([(40, 118), (40, 70), (190, 70), (190, 82)]) + [A('MUL', 'BR')], 'E'),
        ([A('MUL', 'BF')] + o([(202, 150), (-15, 150), (-15, 88)]) +
         [A('BREL', 'BF')], 'E'),
        ([A('MUL', 'PP')] + o([(205, 120), (212, 120)]) + [A('ACC', 'PP')], 'S'),
        ([A('ACC', 'CF')] + o([(201, 185), (135, 185), (135, 161)]) +
         [A('CREL', 'CF')], 'E'),
        ([A('CREL', 'CR')] + o([(148, 162), (148, 155), (201, 155)]) + [A('ACC', 'CR')], 'S'),
        ([A('PCNT', 'CTL')] + o([(246, 171)]) + [A('ACC', 'CTL')], 'W'),
        ([A('SPL', 'CP')] + o([(14, -100), (242, -100)]) + [A('PCNT', 'CP')], 'S'),
        ([A('INREL', 'CR')] + o([(-77, -130), (5, -130)]) + [A('SPL', 'IN')], 'S'),
    ]
    if io:
        g.room(*P['I'], 3, 3)
        g.put(P['I'][0] + 1, P['I'][1] + 1, 'I')
        g.room(*P['O'], 3, 3)
        g.put(P['O'][0] + 1, P['O'][1] + 1, 'O')
        wires.append(([(P['I'][0] + 3, P['I'][1] + 1), (P['I'][0] + 5, P['I'][1] + 1),
                       (P['I'][0] + 5, P['I'][1] + 3)] + [A('INREL', 'CF')], 'E'))
        wires.append(([A('ACC', 'OUT')] + o([(214, 191)]) +
                      [(P['O'][0] - 1, P['O'][1] + 1)], 'E'))
    for pts, ed in wires:
        pipe(g, pts, end_direction=ed)
    return rm, A('INREL', 'CF'), A('ACC', 'OUT')


def build():
    g = Grid()
    engine(g, 0, 0, io=True)
    return g


if __name__ == '__main__':
    g = build()
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/mmpar_e1.man'
    open(path, 'w').write(g.render() + "\n")
    w, h, box = g.footprint()
    print(f"footprint {w}x{h} box={box} -> {path}")
    o = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'grade_fast.py'),
                        'matmul', path], capture_output=True, text=True)
    print(o.stdout.strip()[:400] or o.stderr.strip()[:400])
