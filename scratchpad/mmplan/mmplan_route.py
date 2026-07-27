#!/usr/bin/env python3
"""Route all 18 P=2 nets over a given placement and report exactly which fail.

build_p4 dies inside its four HAND-routed engine pipes, before its negotiated
router ever runs, so "P=2 is blocked on planarity" has never actually been
tested end-to-end on this placement. This routes every net with one uniform
BFS under the real rules and reports per-net success, so the failure is
attributable to a net rather than to a stage.

Rules applied:
  * a pipe may hug a foreign ROOM WALL, but may not touch another PIPE
    (two adjacent pipes parse as one) -- so pipes get a 1-cell halo, rooms none
  * endpoints are fixed by the port table, so each net is a plain 2-point BFS

usage: mmplan_route.py [ey2]
"""
import os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'scratchpad', 'mmpar'))
from mm2lib import Grid                      # noqa: E402
import p3rooms as P3                         # noqa: E402
import prooms as P                           # noqa: E402
import build_e1 as E                         # noqa: E402

# FLOORPLAN v2: each engine sits immediately RIGHT of its own FE, so FE->ENG is
# a short local hop instead of a 900-cell traversal; MRG sits right of both
# engines, collecting O1 from above and O2 from the left; the glue column stays
# left of the FEs. Engines are 268x286, so the two FEs must be ~350 apart in y.
E1 = (605, 311)      # engine 1 origin: bbox x[590,857] y[211,496]
E2 = (605, 661)      # engine 2 origin: bbox x[590,857] y[561,846]
GPOS = dict(I=(400, 460), BC=(430, 460), ADMX=(430, 400), BDUP=(430, 510),
            MCTLA=(470, 400), MCTLC=(470, 520),
            FE1=(560, 300), FE2=(560, 650), MRG=(880, 480), O=(910, 486))

g = Grid()
e1, in1, out1 = E.engine(g, *E1, io=False)
e2, in2, out2 = E.engine(g, *E2, io=False)
rm = {}
for k in ('I', 'O'):
    g.room(*GPOS[k], 3, 3)
g.put(GPOS['I'][0] + 1, GPOS['I'][1] + 1, 'I')
g.put(GPOS['O'][0] + 1, GPOS['O'][1] + 1, 'O')
rm['BC'] = P3.bcst(g, *GPOS['BC'])
rm['ADMX'] = P3.admx3(g, *GPOS['ADMX'])
rm['BDUP'] = P3.bdup2(g, *GPOS['BDUP'])
rm['MCTLA'] = P3.mctl3(g, *GPOS['MCTLA'], 'M', True)
rm['MCTLC'] = P3.mctl3(g, *GPOS['MCTLC'], 'K', False)
rm['FE1'] = P3.fe(g, *GPOS['FE1'], '1')
rm['FE2'] = P3.fe(g, *GPOS['FE2'], '2')
rm['MRG'] = P.mrg(g, *GPOS['MRG'])
A = lambda n, p: (rm[n].pipes[p][0], rm[n].pipes[p][1])

NETS = [
    ('I->BC', (GPOS['I'][0] + 1, GPOS['I'][1] + 3), A('BC', 'IN')),
    ('BC->ADMX', A('BC', 'OA'), A('ADMX', 'AP')),
    ('BC->BDUP', A('BC', 'OB'), A('BDUP', 'BI')),
    ('BC->FE1', A('BC', 'OH1'), A('FE1', 'HI')),
    ('BC->FE2', A('BC', 'OH2'), A('FE2', 'HI')),
    ('ADMX->MCTLA', A('ADMX', 'MCA'), A('MCTLA', 'MI')),
    ('MCTLA->ADMX', A('MCTLA', 'MO'), A('ADMX', 'MA')),
    ('ADMX->MCTLC', A('ADMX', 'MCC'), A('MCTLC', 'MI')),
    ('MCTLC->MRG', A('MCTLC', 'MO'), A('MRG', 'MC')),
    ('ADMX->FE1', A('ADMX', 'AO1'), A('FE1', 'DA')),
    ('ADMX->FE2', A('ADMX', 'AO2'), A('FE2', 'DA')),
    ('BDUP->FE1', A('BDUP', 'BO1'), A('FE1', 'DB')),
    ('BDUP->FE2', A('BDUP', 'BO2'), A('FE2', 'DB')),
    ('MRG->O', A('MRG', 'OUT'), (GPOS['O'][0] - 1, GPOS['O'][1] + 1)),
    ('FE1->ENG1', A('FE1', 'FO'), in1),
    ('FE2->ENG2', A('FE2', 'FO'), in2),
    ('ENG1->MRG', out1, A('MRG', 'O1')),
    ('ENG2->MRG', out2, A('MRG', 'O2')),
]

occ = {c for c, ch in g.c.items() if ch != ' '}
xs = [c[0] for c in occ]; ys = [c[1] for c in occ]
X0, X1 = min(xs) - 200, max(xs) + 200
Y0, Y1 = min(ys) - 200, max(ys) + 200
print(f'placement bbox x[{min(xs)},{max(xs)}] y[{min(ys)},{max(ys)}]  '
      f'search x[{X0},{X1}] y[{Y0},{Y1}]')

blocked = set(occ)
laid = []


def bfs(src, dst, blocked):
    if src == dst:
        return [src]
    seen = {src: None}
    q = deque([src])
    while q:
        c = q.popleft()
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + d[0], c[1] + d[1])
            if not (X0 <= n[0] <= X1 and Y0 <= n[1] <= Y1) or n in seen:
                continue
            if n != dst and n in blocked:
                continue
            seen[n] = c
            if n == dst:
                path, k = [], n
                while k is not None:
                    path.append(k); k = seen[k]
                return path[::-1]
            q.append(n)
    return None


ok = 0
for name, s, d in NETS:
    p = bfs(s, d, blocked)
    if p is None:
        print(f'  {name:14s} FAIL  {s} -> {d}')
        continue
    ok += 1
    halo = set(p)
    for (x, y) in p:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            halo.add((x + dx, y + dy))
    blocked |= halo
    laid.append((name, p))
    print(f'  {name:14s} ok    len {len(p)}')
print(f'\n{ok}/{len(NETS)} nets routed')
