#!/usr/bin/env python3
"""evict.py — empty a whole interior row by re-routing EVERY connector that keeps it alive.

tools/reroute.py moves one connector at a time and only when that single move frees a row.
Most surviving connector rows are held by two or more independent runs, so nothing moves.
This pass picks a target row, rips all private op-free connector runs whose glyphs sit on
it, and re-routes each one with that row (and every row emptied so far) forbidden.

usage: evict.py <in.man> <out.man> [--slug gradebook]
"""
import sys, os, heapq, subprocess, json, tempfile

REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf
import reroute as RR

E, W, S, N = (1, 0), (-1, 0), (0, 1), (0, -1)
TURN_OF = {E: ">", W: "<", S: "v", N: "^"}
EMPTY_ROW_COST = 500
BEND_COST = 3
STEP_COST = 1


def route(g, st, occupied_rows, forbid_rows, ripped, s0, end_state, end_is_turn,
          max_nodes=400000):
    (ex, ey), ed = end_state
    ripped_cells = {c for c, _ in ripped}

    def other_flows(cell):
        f = set(st.get(cell, set()))
        for (c2, d2) in ripped:
            if c2 == cell and d2 in f:
                f.discard(d2)
        return f

    hq = [(0, 0, s0, None)]
    best, parent, counter, goal = {}, {}, 0, None
    while hq:
        cost, _, cur, par = heapq.heappop(hq)
        if cur in best and best[cur] <= cost:
            continue
        best[cur] = cost
        parent[cur] = par
        (x, y), d = cur
        if (x, y) == (ex, ey) and (end_is_turn or d == ed):
            goal = cur
            break
        counter += 1
        if counter > max_nodes:
            break
        ch = g.at(x, y)
        blank = ch == " " or (x, y) in ripped_cells
        if not blank or not g.walkable(x, y):
            continue
        for nd in (E, W, S, N):
            if nd == (-d[0], -d[1]):
                continue
            turn = nd != d
            if turn:
                if other_flows((x, y)):
                    continue
                if y in forbid_rows:
                    continue          # no glyph may land on an evicted row
            ncell = (x + nd[0], y + nd[1])
            c2 = cost + STEP_COST + (BEND_COST if turn else 0)
            if ncell[1] not in occupied_rows and ncell != (ex, ey):
                c2 += EMPTY_ROW_COST
            nstate = (ncell, nd)
            if nstate not in best or best[nstate] > c2:
                heapq.heappush(hq, (c2, counter, nstate, cur))
    if goal is None:
        return None
    path, cur = [], goal
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()
    return path


def grid_of(rows):
    g = wf.Grid(rows)
    succ = g.walk(g.starts()[0])
    st = wf.state_map(succ)
    return g, succ, st


def glyph_rows(g, rows):
    (rx0, ry0), (rx1, ry1) = g.rooms[0]["min"], g.rooms[0]["max"]
    res = {}
    for y in range(ry0 + 1, ry1):
        cs = [x for x in range(rx0 + 1, rx1) if g.at(x, y) != " "]
        if cs:
            res[y] = cs
    return res


REASON = []


def try_evict(rows, y, forbid):
    """Return new rows if row y can be fully emptied, else None."""
    work = [r[:] if isinstance(r, list) else r for r in rows]
    for _ in range(12):
        g, succ, st = grid_of(work)
        (rx0, ry0), (rx1, ry1) = g.rooms[0]["min"], g.rooms[0]["max"]
        cs = [x for x in range(rx0 + 1, rx1) if g.at(x, y) != " "]
        if not cs:
            return work
        if any(g.at(x, y) not in "><^vV" for x in cs):
            REASON.append(f"row {y}: real op")
            return None                      # real op on the row
        conns = RR.find_connectors(g, succ, st)
        target = None
        for states, s0, end in conns:
            if not RR.private_to(g, states, st):
                continue
            if any(g.at(*c) != " " and c[1] == y for c, _ in states):
                target = (states, s0, end)
                break
        if target is None:
            REASON.append(f"row {y}: no private connector on it (cols {cs})")
            return None
        states, s0, end = target
        gr = glyph_rows(g, work)
        ripcells = {c for c, _ in states if g.at(*c) != " "}
        occ = {yy for yy, xs in gr.items() if any((x, yy) not in ripcells for x in xs)}
        occ -= forbid | {y}
        end_is_turn = g.at(*end[0]) in "><^vV"
        path = route(g, st, occ, forbid | {y}, states, s0, end, end_is_turn)
        if path is None:
            REASON.append(f"row {y}: no route for connector at {s0} -> {end}")
            return None
        work = ["".join(r) for r in RR.apply_route(work, states, path)]
    REASON.append(f"row {y}: iteration limit")
    return None


def sig_ok(rows, base_sig):
    fd, tmp = tempfile.mkstemp(suffix=".man")
    os.close(fd)
    open(tmp, "w").write(wf.render([list(r) for r in rows]))
    try:
        ok = RR.signature(tmp) == base_sig
    except Exception:
        ok = False
    os.unlink(tmp)
    return ok


def main():
    src, out = sys.argv[1], sys.argv[2]
    base_sig = RR.signature(src)
    rows = wf.load_rows(src)
    forbid = set()
    done = []
    for _ in range(40):
        g, _, _ = grid_of(rows)
        gr = glyph_rows(g, rows)
        cands = [y for y, xs in sorted(gr.items(), key=lambda kv: len(kv[1]))
                 if y not in forbid and all(g.at(x, y) in "><^vV" for x in xs)]
        moved = False
        for y in cands:
            new = try_evict(rows, y, forbid)
            if new is None:
                continue
            if not sig_ok(new, base_sig):
                REASON.append(f"row {y}: signature changed")
                continue
            rows = new
            forbid.add(y)
            done.append(y)
            print(f"  evicted row {y} (total {len(done)})")
            moved = True
            break
        if not moved:
            break
    open(out, "w").write(wf.render([list(r) for r in rows]))
    print(f"wrote {out}; evicted {done}")
    if os.environ.get("EVICT_VERBOSE"):
        for r in REASON[-60:]:
            print("   ", r)


main()
