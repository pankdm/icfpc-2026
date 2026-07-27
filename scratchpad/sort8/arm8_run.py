#!/usr/bin/env python3
"""Drive the arm8 search: enumerate, assemble, emit .man, grade."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arm8 import DIRCH, INTERIOR, OUTER, S_OUT_X, loop_cells, render, REPO
import arm8_search as S

OUTDIR = os.path.dirname(os.path.abspath(__file__)) + "/cand"
os.makedirs(OUTDIR, exist_ok=True)
from collections import Counter
FAIL = Counter()


def assemble(ux, uy, cand):
    loop = loop_cells(ux, uy)
    gate = (ux + 1, uy + 1)
    cells = dict(cand["cells"])
    free = set(INTERIOR) - set(loop) - set(cells)
    order = cand["order"]
    ypos, ydir, obirth = cand["y"]

    # ---- output man first (most constrained: 's' must sit at x<=3)
    bdir = (obirth[0] - ypos[0], obirth[1] - ypos[1])

    def ogoal(pos, nd, noi, c):
        if noi == 2:
            nn = (pos[0] + nd[0], pos[1] + nd[1])
            if nn in free and nn not in c:
                c = dict(c)
                c[nn] = 'H'
                return c
        return None

    om = S.walk(obirth, bdir, free, ['W', 's'], ogoal, maxlen=14,
                xlimit={'s': set(S_OUT_X)})
    if om is None:
        FAIL['outman'] += 1
        return None
    cells.update(om)
    free -= set(om)

    # ---- round branch: R n, b (+ any lap ops it skips) then merge into the lap
    entries = {((ux + 1, uy + 2), (0, -1)), ((ux + 2, uy + 1), (-1, 0))}
    entries = {e for e in entries if 1 <= e[0][0] <= 8 and 1 <= e[0][1] <= 7}
    other = [e for e in entries if e != cand["entry"] and e[0] in free]
    oe = other[0] if other else None
    qpos = [p for p in order if cells.get(p) == 'q'][0]
    lim = max(order.index(ypos), order.index(qpos))
    ti = order.index(cand["test"])
    tex, tdir = cand["texit"]

    plans = []
    for i in range(lim + 1, len(order)):
        C = order[i]
        if cells.get(C) not in '<>^v':
            continue
        pre = [cells[p] for p in order[max(ti + 1, 0):i] if cells[p] in ('m', 'R', 'M')]
        plans.append((['R', 'b'] + pre, C, None))
    if oe:
        plans.append((['R', 'b', 'm', 'R', 'M'], None, oe))
    plans.sort(key=lambda pl: len(pl[0]))

    rb = None
    for ops, C, ent in plans:
        def rgoal(pos, nd, noi, c, C=C, ent=ent, n=len(ops)):
            nn = (pos[0] + nd[0], pos[1] + nd[1])
            if noi != n:
                return None
            if C is not None and nn == C:
                return c
            if ent is not None and (pos, nd) == ent and nn == gate:
                return c
            return None
        rb = S.walk(tex, tdir, free, ops, rgoal, maxlen=20)
        if rb is not None:
            break
    if rb is None:
        FAIL['round'] += 1
        return None
    cells.update(rb)
    free -= set(rb)

    # ---- '@' : corridor of absolute-dir cells into the start of the round chain
    tgt = {}
    tgt[tex] = None if cells.get(tex) in '<>^v' else tdir
    for i in range(order.index(ypos) + 1, ti):
        p = order[i]
        if cells.get(p) in '<>^v':
            tgt[p] = None
    # backward BFS over free cells
    reach = {}
    frontier = list(tgt)
    while frontier:
        nxt = []
        for t in frontier:
            for d in DIRCH:
                c = (t[0] - d[0], t[1] - d[1])
                if c not in free or c in reach:
                    continue
                if tgt.get(t) is not None and t in tgt and tgt[t] != d:
                    continue
                reach[c] = (d, t)
                nxt.append(c)
        frontier = nxt
    pool = set(free) | {k for k, v in cells.items() if v == ' '}
    at = None
    for f in sorted(pool):
        e = (f[0] + 1, f[1])
        if e in tgt and (tgt[e] is None or tgt[e] == (1, 0)):
            at = f
            break
        if e in reach:
            at = f
            break
    if at is None:
        FAIL['at'] += 1
        return None
    cells[at] = '@'
    free.discard(at)
    cur = (at[0] + 1, at[1])
    while cur in reach:
        d, nxt = reach[cur]
        cells[cur] = DIRCH[d]
        free.discard(cur)
        cur = nxt

    g = dict(OUTER)
    for k, v in loop.items():
        g[k] = v
    for k, v in cells.items():
        if v == ' ':
            continue
        if k in g:
            FAIL['gclash'] += 1
            return None
        g[k] = v
    return render(g)


def main():
    cands = []
    for ux in range(5, 8):
        for uy in range(2, 7):
            loop = loop_cells(ux, uy)
            if any(not (1 <= x <= 8 and 1 <= y <= 7) for (x, y) in loop):
                continue
            m0 = (ux + 1, uy - 1)
            free = set(INTERIOR) - set(loop) - {m0}
            appr = [(ux + 1, uy + 2), (ux + 2, uy + 1)]
            if any(not (1 <= a[0] <= 8 and 1 <= a[1] <= 7) for a in appr):
                continue
            for res in appr:
                for c in S.lap_paths(ux, uy, free, maxlen=17, reserved=res):
                    cands.append((c["ticks"], ux, uy, c))
    cands.sort(key=lambda t: t[0])
    print("lap-chain candidates:", len(cands),
          "best ticks:", cands[0][0] if cands else None)

    seen, emitted = set(), []
    for ticks, ux, uy, c in cands:
        if len(emitted) >= int(sys.argv[1] if len(sys.argv) > 1 else 60):
            break
        txt = assemble(ux, uy, c)
        if txt is None or txt in seen:
            continue
        seen.add(txt)
        name = "%s/arm8_%d_%d_%d_%03d.man" % (OUTDIR, ticks, ux, uy, len(emitted))
        open(name, "w").write(txt)
        emitted.append((ticks, name))
    print("emitted:", len(emitted), dict(FAIL))

    results = []
    for ticks, name in emitted:
        out = subprocess.run([sys.executable, REPO + "/tools/grade_fast.py",
                              "sort-numbers", name],
                             capture_output=True, text=True).stdout.strip()
        try:
            d = json.loads(out)
        except Exception:
            results.append((ticks, name, "ERR", out[:80]))
            continue
        results.append((ticks, name, d["passed"], d.get("score"), d.get("avgTicks")))
    ok = [r for r in results if r[2] == 7]
    ok.sort(key=lambda r: r[3])
    print("passing 7/7:", len(ok), "of", len(results))
    for r in ok[:8]:
        print("  ", r[0], os.path.basename(r[1]), r[3], r[4])
    if not ok:
        from collections import Counter
        print(Counter([str(r[2]) for r in results]).most_common(6))
        for r in results[:5]:
            print("  ", os.path.basename(r[1]), r[2:])


if __name__ == "__main__":
    main()
