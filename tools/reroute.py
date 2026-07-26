#!/usr/bin/env python3
"""reroute — rip up op-free connector paths of man0 and re-route them through
already-populated rows, so donor rows empty and squash can delete them.

A connector is a maximal run of walk states over blanks and PRIVATE turn glyphs
between two anchors (op cells, branch cells, or any cell another flow touches).
The replacement path must reproduce the same departure state and reach the same
anchor with the same post-anchor behavior (exact arrival state, or any arrival
direction when the anchor is a plain turn glyph).

Cost: entering a row that holds no other glyph is expensive (it keeps the row
alive); steps and bends are cheap. So routes hug populated rows and verticals.
"""
import sys, os, heapq

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

E, W, S, N = (1, 0), (-1, 0), (0, 1), (0, -1)
TURN_OF = {E: ">", W: "<", S: "v", N: "^"}
EMPTY_ROW_COST = 500
BEND_COST = 3
STEP_COST = 1


def find_connectors(g, succ, st):
    """Yield (states, start_state, end_state) for each maximal op-free private run."""
    # entry points: successors of anchor states
    def is_anchor_cell(c):
        ch = g.at(*c)
        return ch != " " and ch not in "><^vV"

    conns = []
    seen_starts = set()
    for (c, d), ns in succ.items():
        if not ns:
            continue
        ch = g.at(*c)
        starts = []
        if ch in wf.BRANCH:
            starts = [n for n in ns]
        elif is_anchor_cell(c) or ch == "@":
            starts = ns
        else:
            continue
        for s0 in starts:
            if s0 in seen_starts:
                continue
            seen_starts.add(s0)
            # walk forward through private turn/blank cells
            states = []
            cur = s0
            ok = True
            visited = set()
            while True:
                if cur in visited:
                    ok = False   # closed op-free loop: leave alone
                    break
                visited.add(cur)
                (x, y), d2 = cur
                if not g.walkable(x, y):
                    ok = False
                    break
                cch = g.at(x, y)
                if is_anchor_cell((x, y)):
                    break        # reached the next anchor
                if cch in "><^vV" and (st.get((x, y), set()) - {d2}):
                    break        # shared turn glyph: a merge point, treat as anchor
                states.append(cur)
                nxt = succ.get(cur, [])
                if len(nxt) != 1:
                    ok = False
                    break
                cur = nxt[0]
            if not ok or not states:
                continue
            conns.append((states, s0, cur))
    return conns


def private_to(g, states, st):
    """True if every GLYPH cell in the run is touched only by this run's own flow.
    Blank glide cells may be shared: nothing is erased there."""
    dirs_at = {}
    for ((x, y), d) in states:
        dirs_at.setdefault((x, y), set()).add(d)
    for cell, dirs in dirs_at.items():
        if g.at(*cell) != " " and st.get(cell, set()) != dirs:
            return False
    return True


def route(g, st, occupied_rows, ripped, s0, end_state, end_is_turn, max_nodes=200000):
    """A* from state s0 to the end anchor. Returns list of (cell, dir) states or None.

    ripped: cells of the old connector (treated as blank).
    A glyph may be written only on a cell that is blank (or ripped) and carries
    no other flow. Glide cells must be blank (or ripped); other flows may share
    them only while we do NOT write a glyph there (handled at reconstruction:
    a state where direction changes writes a glyph; a pass-through does not)."""
    (ex, ey), ed = end_state

    def flows(cell):
        f = st.get(cell, set())
        return f - {d for (c, d) in ripped_states.get(cell, ())}

    # precompute: st minus the ripped run's own contribution
    ripped_states = {}
    for (c, d) in ripped:
        ripped_states.setdefault(c, set()).add((c, d))

    def other_flows(cell):
        f = set(st.get(cell, set()))
        for (c2, d2) in ripped:
            if c2 == cell and d2 in f:
                f.discard(d2)
        return f

    start = s0
    hq = [(0, 0, start, None)]
    best = {}
    parent = {}
    counter = 0
    goal = None
    while hq:
        cost, _, cur, par = heapq.heappop(hq)
        if cur in best and best[cur] <= cost:
            continue
        best[cur] = cost
        parent[cur] = par
        (x, y), d = cur
        # goal test: at end cell with right arrival
        if (x, y) == (ex, ey):
            if end_is_turn or d == ed:
                goal = cur
                break
            continue
        counter += 1
        if counter > max_nodes:
            break
        ch = g.at(x, y)
        cell_ripped = ((x, y), d) in ripped or any(c == (x, y) for c, _ in ripped)
        blank = ch == " " or any(c == (x, y) for c, _ in ripped)
        if not blank:
            continue                    # cannot use an existing glyph cell
        if not g.walkable(x, y):
            continue
        for nd in (E, W, S, N):
            if nd == (-d[0], -d[1]):
                continue
            turn = nd != d
            if turn:
                # writing a turn glyph here: no other flow may touch this cell
                if other_flows((x, y)):
                    continue
            ncell = (x + nd[0], y + nd[1])
            nstate = (ncell, nd)
            c2 = cost + STEP_COST + (BEND_COST if turn else 0)
            ny = ncell[1]
            if ny not in occupied_rows and ncell != (ex, ey):
                c2 += EMPTY_ROW_COST
            if nstate not in best or best[nstate] > c2:
                heapq.heappush(hq, (c2, counter, nstate, cur))
    if goal is None:
        return None
    # reconstruct
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()
    return path


def apply_route(rows, old_states, new_path):
    patch = {}
    for ((x, y), d) in old_states:
        patch[f"{x},{y}"] = " "
    # write turn glyphs where direction changes along the new path (excluding
    # the final anchor cell)
    for i in range(len(new_path) - 1):
        (c, d) = new_path[i]
        (c2, d2) = new_path[i + 1]
        if d2 != d:
            patch[f"{c[0]},{c[1]}"] = TURN_OF[d2]
    return wf.apply_patch(rows, patch)


def signature(path):
    import blockify3
    blocks = blockify3.lift(path)
    sig = []
    for b in blocks:
        term = b["term"]
        if term[0] == "branch":
            legs = {k: (v[0], v[1] if v[0] == "block" else None)
                    for k, v in term[2].items()}
            t = ("branch", term[1], tuple(sorted(legs.items())))
        elif term[0] == "wall":
            t = ("wall",)
        else:
            t = term
        sig.append((tuple(b["ops"][i][0] for i in range(len(b["ops"]))),
                    tuple(str(b["ops"][i][1]) for i in range(len(b["ops"]))),
                    t))
    return sig


def main():
    src, out = sys.argv[1], sys.argv[2]
    import tempfile, shutil
    base_sig = signature(src)
    rows = wf.load_rows(src)
    total = 0
    for rnd in range(60):
        g = wf.Grid(rows)
        succ = g.walk(g.starts()[0])
        st = wf.state_map(succ)
        (rx0, ry0), (rx1, ry1) = g.rooms[0]["min"], g.rooms[0]["max"]
        conns = find_connectors(g, succ, st)
        # occupied rows: interior rows with any glyph
        def occ_rows(exclude_cells=()):
            ex = {c for c, _ in exclude_cells}
            res = set()
            for y in range(ry0 + 1, ry1):
                for x in range(rx0 + 1, rx1):
                    if g.at(x, y) != " " and (x, y) not in ex:
                        res.add(y)
                        break
            return res

        # rank: connectors whose private glyph rows would empty
        cands = []
        for states, s0, end in conns:
            if not private_to(g, states, st):
                continue
            glyph_cells = [(c, d) for (c, d) in states if g.at(*c) != " "]
            if not glyph_cells:
                continue
            rows_touched = {c[1] for c, _ in glyph_cells}
            occ_wo = occ_rows(exclude_cells=glyph_cells)
            would_free = [y for y in rows_touched if y not in occ_wo]
            cands.append((len(would_free), len(glyph_cells), states, s0, end))
        cands.sort(key=lambda t: (-t[0], -t[1]))
        applied = False
        for wf_, ng, states, s0, end in cands:
            glyph_cells = [(c, d) for (c, d) in states if g.at(*c) != " "]
            occ_wo = occ_rows(exclude_cells=glyph_cells)
            end_cell, end_d = end
            end_is_turn = g.at(*end_cell) in "><^vV"
            path = route(g, st, occ_wo, states, s0, end, end_is_turn)
            if path is None:
                continue
            # improvement test: new rows kept vs old rows kept
            old_rows = {c[1] for c, _ in glyph_cells}
            new_glyphs = set()
            for i in range(len(path) - 1):
                if path[i + 1][1] != path[i][1]:
                    new_glyphs.add(path[i][0])
            new_kept = {y for (x, y) in new_glyphs if y not in occ_wo}
            old_kept = {y for y in old_rows if y not in occ_wo}
            if len(new_kept) >= len(old_kept):
                continue
            cand_rows = ["".join(r) for r in apply_route(rows, states, path)]
            # verify signature unchanged
            fd, tmp = tempfile.mkstemp(suffix=".man")
            os.close(fd)
            open(tmp, "w").write(wf.render([list(r) for r in cand_rows]))
            try:
                ok = signature(tmp) == base_sig
            except Exception as exc:
                ok = False
            os.unlink(tmp)
            if not ok:
                continue
            rows = cand_rows
            total += 1
            applied = True
            print(f"  round {rnd}: rerouted connector at {states[0][0]} "
                  f"({len(old_kept)} -> {len(new_kept)} kept rows)")
            break
        if not applied:
            break
    open(out, "w").write(wf.render([list(r) for r in rows]))
    print(f"wrote {out} ({total} connectors rerouted)")


if __name__ == "__main__":
    main()
