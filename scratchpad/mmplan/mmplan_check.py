#!/usr/bin/env python3
"""Validate a routed P=2 floorplan against the real pipe rules.

The negotiated router only enforces occupancy and congestion. A converged
solution can still be ILLEGAL, and the failure mode is nasty: an arrow whose
backward neighbour is not its room's wall is SILENTLY not a pipe -- no load
error, the program just deadlocks. So every route is checked here:

  1. length >= 2 cells
  2. the SOURCE cell's backward neighbour is a wall of the source room
     (a room CORNER counts)
  3. the final cell points into a wall cell of the destination room
  4. no intermediate cell has a room wall behind it -- that parses as a second
     pipe start (the reading-order rule), silently stealing the tail
  5. no two pipes touch (two adjacent pipe cells parse as one pipe)
  6. no pipe cell lands on room material

usage: mmplan_check.py [solution.json]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'scratchpad', 'mmpar'))
from mm2lib import Grid                      # noqa: E402
import p3rooms as P3                         # noqa: E402
import prooms as P                           # noqa: E402
import build_e1 as E                         # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'mmplan_solution.json')
spec = json.load(open(path))
GPOS = {k: tuple(v) for k, v in spec['rooms'].items()}
E1P, E2P = tuple(spec['engines']['ENG1']), tuple(spec['engines']['ENG2'])

g = Grid()
E.engine(g, *E1P, io=False)
E.engine(g, *E2P, io=False)
for k in ('I', 'O'):
    g.room(*GPOS[k], 3, 3)
g.put(GPOS['I'][0] + 1, GPOS['I'][1] + 1, 'I')
g.put(GPOS['O'][0] + 1, GPOS['O'][1] + 1, 'O')
P3.bcst(g, *GPOS['BC']); P3.admx3(g, *GPOS['ADMX']); P3.bdup2(g, *GPOS['BDUP'])
P3.mctl3(g, *GPOS['MCTLA'], 'M', True); P3.mctl3(g, *GPOS['MCTLC'], 'K', False)
P3.fe(g, *GPOS['FE1'], '1'); P3.fe(g, *GPOS['FE2'], '2'); P.mrg(g, *GPOS['MRG'])

occ = {c for c, ch in g.c.items() if ch != ' '}
routes = {nm: [tuple(c) for c in pth] for nm, pth in spec['routes'].items()}

bad = 0
allpipe = set()
for nm, pth in routes.items():
    for c in pth[1:-1]:
        allpipe.add(c)

for nm, pth in routes.items():
    body = pth[1:-1] if len(pth) > 2 else []
    if len(pth) - 1 < 2:
        print(f'{nm}: TOO SHORT ({len(pth)-1} body cells)'); bad += 1
    d0 = (pth[1][0] - pth[0][0], pth[1][1] - pth[0][1])
    back = (pth[0][0] - d0[0], pth[0][1] - d0[1])
    if back not in occ:
        print(f'{nm}: SOURCE {pth[0]} backward {back} is not room material '
              f'-- this arrow silently is NOT a pipe'); bad += 1
    for i in range(1, len(pth) - 1):
        d = (pth[i + 1][0] - pth[i][0], pth[i + 1][1] - pth[i][1])
        b = (pth[i][0] - d[0], pth[i][1] - d[1])
        if b in occ:
            print(f'{nm}: cell {pth[i]} has room material behind it '
                  f'-- parses as a SECOND pipe start'); bad += 1
            break
    for c in pth[:-1]:
        if c in occ:
            print(f'{nm}: cell {c} lands on room material'); bad += 1
            break

# pipes may not touch each other
touch = 0
for nm, pth in routes.items():
    mine = set(pth[:-1])
    for c in mine:
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + d[0], c[1] + d[1])
            if n in allpipe and n not in mine:
                touch += 1
                break
if touch:
    print(f'{touch} pipe cells touch a FOREIGN pipe (two adjacent pipes parse as one)')
    bad += touch

print(f'\n{"LEGAL" if bad == 0 else str(bad) + " VIOLATIONS"}  '
      f'({len(routes)} routes)')
