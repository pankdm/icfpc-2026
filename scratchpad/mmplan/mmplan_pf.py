#!/usr/bin/env python3
"""PathFinder-style negotiated router for the P=2 matmul netlist.

Greedy sequential BFS cannot solve this: routing short nets first starves the
two long engine nets (13/18), routing long nets first starves the glue cluster
(9/18). Both are ordering artifacts, not evidence of an unroutable netlist --
the netlist is already planar ({BC,ADMX,BDUP} x {FE1,FE2} = K(3,2)).

Negotiated congestion fixes exactly this: every net routes on a shared grid and
pays a price for cells others want, the price rises each iteration, and nets
that have a cheap detour take it while nets with no alternative keep their cell.

  cost(c) = 1 + present(c)*PFAC + history(c)
  present(c) = max(0, users(c) - 1)      history grows on any overused cell

Clearance rule (measured): a pipe may hug a foreign ROOM WALL but may not touch
another PIPE -- two adjacent pipes parse as one. So a cell is "used" by a net if
the net occupies it OR is orthogonally adjacent to it.

usage: mmplan_pf.py [iters]
"""
import heapq, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'scratchpad', 'mmpar'))
from mm2lib import Grid                      # noqa: E402
import p3rooms as P3                         # noqa: E402
import prooms as P                           # noqa: E402
import build_e1 as E                         # noqa: E402

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
# Engines beside their own FEs: FE->ENG becomes a short hop instead of ~900
# cells, and the routable region shrinks ~3x, which is what makes negotiated
# routing affordable at all.
# v3: same planar order, but the glue column is SPREAD (40-90 cell gaps) so the
# nets crossing it are not forced through one corridor. Box last, correctness
# first -- the ~350 permanently overused cells at v2 spacing were congestion in
# the glue cluster, not an unroutable netlist.
E1P = (650, 261)     # bbox x[635,902] y[161,446]; IN (655,260) OUT (864,437)
E2P = (650, 711)     # bbox x[635,902] y[611,896]; IN (655,710) OUT (864,887)
GPOS = dict(I=(330, 470), BC=(360, 465), ADMX=(360, 380), BDUP=(360, 560),
            MCTLA=(400, 350), MCTLC=(400, 600),
            FE1=(560, 250), FE2=(560, 700), MRG=(950, 470), O=(990, 476))

g = Grid()
e1, in1, out1 = E.engine(g, *E1P, io=False)
e2, in2, out2 = E.engine(g, *E2P, io=False)
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
X0, X1 = min(xs) - 40, max(xs) + 40
Y0, Y1 = min(ys) - 40, max(ys) + 40
print(f'search x[{X0},{X1}] y[{Y0},{Y1}]  {len(NETS)} nets')

NB = ((1, 0), (-1, 0), (0, 1), (0, -1))
history = {}
routes = {}
# Classic PathFinder schedule: present-cost starts gentle and GROWS each
# iteration while history accumulates. A large constant present-cost makes nets
# thrash between corridors instead of settling (measured: 325 -> 622).
PFAC = 0.5


def footprint(path):
    """cells this net makes unusable: the path plus its 1-cell pipe halo."""
    f = set(path)
    for (x, y) in path:
        for dx, dy in NB:
            f.add((x + dx, y + dy))
    return f


def route(src, dst, users, self_name, PFAC=None):
    """Dijkstra over congestion cost; endpoints are exempt from halo cost."""
    dist = {src: 0.0}
    prev = {src: None}
    pq = [(0.0, src)]
    while pq:
        d, c = heapq.heappop(pq)
        if d > dist.get(c, 1e18):
            continue
        if c == dst:
            break
        for dx, dy in NB:
            n = (c[0] + dx, c[1] + dy)
            if not (X0 <= n[0] <= X1 and Y0 <= n[1] <= Y1):
                continue
            if n in occ and n != dst:
                continue
            u = users.get(n, 0)
            if self_name in u if isinstance(u, set) else False:
                pass
            cnt = len(u) - (1 if isinstance(u, set) and self_name in u else 0) \
                if isinstance(u, set) else 0
            cost = 1.0 + PFAC * max(0, cnt) + history.get(n, 0.0)
            nd = d + cost
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                prev[n] = c
                heapq.heappush(pq, (nd, n))
    if dst not in prev:
        return None
    path, k = [], dst
    while k is not None:
        path.append(k); k = prev[k]
    return path[::-1]


for it in range(ITERS):
    users = {}
    for nm, p in routes.items():
        for c in footprint(p):
            users.setdefault(c, set()).add(nm)
    failed = 0
    for nm, s, d in NETS:
        if nm in routes:
            for c in footprint(routes[nm]):
                users[c].discard(nm)
        p = route(s, d, users, nm, PFAC)
        if p is None:
            failed += 1
            routes.pop(nm, None)
            continue
        routes[nm] = p
        for c in footprint(p):
            users.setdefault(c, set()).add(nm)
    over = [c for c, u in users.items() if len(u) > 1]
    for c in over:
        history[c] = history.get(c, 0.0) + 1.0
    PFAC = min(PFAC * 1.7, 400.0)
    print(f'  iter {it:2d}: routed {len(routes)}/{len(NETS)}  '
          f'unroutable {failed}  overused cells {len(over)}', flush=True)
    if not over and len(routes) == len(NETS):
        print('\nLEGAL SOLUTION FOUND', flush=True)
        import json
        spec = dict(engines=dict(ENG1=list(E1P), ENG2=list(E2P)),
                    rooms={k: list(v) for k, v in GPOS.items()},
                    routes={nm: [list(c) for c in pth] for nm, pth in routes.items()})
        out = os.path.join(HERE, 'mmplan_solution.json')
        json.dump(spec, open(out, 'w'), indent=1)
        print('wrote', out, flush=True)
        for nm, pth in routes.items():
            print(f'  {nm:14s} len {len(pth)}')
        break
