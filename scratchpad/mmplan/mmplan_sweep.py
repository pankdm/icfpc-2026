#!/usr/bin/env python3
"""Sweep the GLUE SPACING -- the one thing mmplan_pf never had time to search.

mmplan_pf established that the P=2 netlist routes 18/18 under a uniform BFS once
overlaps are ignored, and that with engines beside their FEs the residue is
~325-420 *permanently* contested cells in the glue cluster.  Its own conclusion:
that is congestion, and it needs wider glue spacing.  This sweeps exactly that.

The glue cluster is I / BC / ADMX / BDUP / MCTLA / MCTLC.  v3 pinned them at
x=330..400, y=350..600.  Here their offsets from the cluster centre are scaled
by (SX, SY), so the sweep is two integers, and everything else (engines, FEs,
MRG, O) stays where it was measured to work.

  python3 scratchpad/mmplan/mmplan_sweep.py [iters] [n_workers]

Reports, per (SX, SY): best (routed, overused) seen and the iteration it hit.
A config reaching overused=0 with routed=18 is a LEGAL floorplan and is written
out as mmplan_solution_<sx>_<sy>.json.
"""
import heapq, itertools, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'scratchpad', 'mmpar'))
from mm2lib import Grid                      # noqa: E402
import p3rooms as P3                         # noqa: E402
import prooms as P                           # noqa: E402
import build_e1 as E                         # noqa: E402

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 12

E1P = (650, 261)
E2P = (650, 711)
# v3 baseline glue positions and the cluster centre they are scaled about.
BASE = dict(I=(330, 470), BC=(360, 465), ADMX=(360, 380), BDUP=(360, 560),
            MCTLA=(400, 350), MCTLC=(400, 600))
FIXED = dict(FE1=(560, 250), FE2=(560, 700), MRG=(950, 470), O=(990, 476))
CX = sum(p[0] for p in BASE.values()) / len(BASE)
CY = sum(p[1] for p in BASE.values()) / len(BASE)
NB = ((1, 0), (-1, 0), (0, 1), (0, -1))


def spread(sx, sy):
    g = dict(FIXED)
    for k, (x, y) in BASE.items():
        g[k] = (int(CX + (x - CX) * sx), int(CY + (y - CY) * sy))
    return g


def footprint(path):
    f = set(path)
    for (x, y) in path:
        for dx, dy in NB:
            f.add((x + dx, y + dy))
    return f


def attempt(sx, sy, iters=ITERS):
    GPOS = spread(sx, sy)
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
    history, routes = {}, {}

    def route(src, dst, users, self_name, pfac):
        dist = {src: 0.0}; prev = {src: None}; pq = [(0.0, src)]
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
                u = users.get(n)
                cnt = (len(u) - (1 if self_name in u else 0)) if u else 0
                nd = d + 1.0 + pfac * max(0, cnt) + history.get(n, 0.0)
                if nd < dist.get(n, 1e18):
                    dist[n] = nd; prev[n] = c
                    heapq.heappush(pq, (nd, n))
        if dst not in prev:
            return None
        path, k = [], dst
        while k is not None:
            path.append(k); k = prev[k]
        return path[::-1]

    pfac = 0.5
    best = (0, 10 ** 9, -1)
    for it in range(iters):
        users = {}
        for nm, p in routes.items():
            for c in footprint(p):
                users.setdefault(c, set()).add(nm)
        for nm, s, d in NETS:
            if nm in routes:
                for c in footprint(routes[nm]):
                    users[c].discard(nm)
            p = route(s, d, users, nm, pfac)
            if p is None:
                routes.pop(nm, None)
                continue
            routes[nm] = p
            for c in footprint(p):
                users.setdefault(c, set()).add(nm)
        over = [c for c, u in users.items() if len(u) > 1]
        for c in over:
            history[c] = history.get(c, 0.0) + 1.0
        pfac = min(pfac * 1.7, 400.0)
        if (len(routes), -len(over)) > (best[0], -best[1]):
            best = (len(routes), len(over), it)
        if not over and len(routes) == len(NETS):
            spec = dict(engines=dict(ENG1=list(E1P), ENG2=list(E2P)),
                        rooms={k: list(v) for k, v in GPOS.items()},
                        routes={nm: [list(c) for c in pth] for nm, pth in routes.items()})
            json.dump(spec, open(os.path.join(HERE, 'mmplan_solution_%g_%g.json' % (sx, sy)), 'w'))
            return (len(routes), 0, it, True)
    return (best[0], best[1], best[2], False)




def _job(a):
    sx, sy, iters = a
    try:
        return (sx, sy) + attempt(sx, sy, iters)
    except Exception as e:                                  # noqa: BLE001
        return (sx, sy, -1, 10 ** 9, -1, False)


def parallel(grid, iters, workers):
    import multiprocessing as mp
    with mp.Pool(workers) as pool:
        for sx, sy, r, ov, it, ok in pool.imap_unordered(
                _job, [(a, b, iters) for a, b in grid]):
            print('sx=%.1f sy=%.1f -> routed %2d/18  best-overused %5d (iter %d)%s'
                  % (sx, sy, r, ov, it, '  *** LEGAL ***' if ok else ''), flush=True)
