#!/usr/bin/env python3
"""smtrows.py — SMT-optimal op placement for flowgrid boustrophedon controllers.

The greedy boustrophedon in flowgrid places each op at the first legal column
and wraps when the next op's pipe band lies behind the cursor. Row count is
the controller's height, and height drives snake's box. This tool asks Z3 for
the true optimum of the same problem, in two phases:

  phase 1  port columns FIXED (current COMPACT_PORTS): how far from optimal is
           the greedy layout? (an optimality certificate if the gap is ~0)
  phase 2  port columns FREE (order fixed, Voronoi bands derived inside the
           model, component-geometry side constraints): the joint optimum that
           no per-block greedy can reach.

Encoding, per block: ints r_i (row), c_i (col). Direction is row parity
(blocks enter east). Same row => strictly monotone cols in the row direction;
row+1 => the drop-column linkage (east->west: c' <= c, west->east: c' >= c).
Port ops must sit inside their pipe's band: strictly nearer their port column
than any other same-direction port (2c >= Pa+Pb+2 / 2c <= Pa+Pb-2 around each
neighbour midpoint), which is exactly the oracle's nearest-pipe rule with the
y-term cancelled. Objective: minimize total op rows, then width.

This measures ONLY controller op rows. Merge bands, X-arm rows and component
rows are constants shared by both layouts.
"""
import argparse
import sys

import z3

sys.path.insert(0, __import__("os").path.dirname(__file__))
import stateflow  # noqa: E402


def load_flow(source, man_index=None, trace=None):
    """A builder exposing build_flow(), OR — via tools/liftflow.py — any .man grid.

    Only two builders in the repo ever exposed build_flow(), so this tool could not be
    pointed at the hand-structured champions (snake's build_fold*, gradebook, tcp) where
    the air actually is. `.man` input goes through the lift instead, which recovers the
    same object (blocks + a port table) from the grid."""
    import importlib.util
    import os
    if source.endswith(".man"):
        import liftflow
        return liftflow.lift_flow(source, man_index=man_index, trace_slug=trace)
    spec = importlib.util.spec_from_file_location("_builder", source)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(source))
    spec.loader.exec_module(mod)
    flow = mod.build_flow()
    if not getattr(flow, "ports", None):
        flow.ports = stateflow.COMPACT_PORTS
    return flow


def block_sequences(flow):
    """Yield (label, [op...]) where op is ('port', name) or ('plain',) or
    ('term', kind)."""
    out = []
    ports = flow.ports
    for label, tokens in flow.blocks.items():
        seq = []
        for t in tokens:
            if isinstance(t, tuple):
                seq.append(("term", t[0]))
                break
            if t in ports:
                seq.append(("port", t))
            else:
                seq.append(("plain",))
        out.append((label, seq))
    return out


def solve(flow, free_ports=False, wmax=155, timeout_ms=180000, min_sep=4, pmin=4):
    ports = flow.ports
    snake_geometry = ports is stateflow.COMPACT_PORTS
    names = list(ports)
    opt = z3.Optimize()
    opt.set("timeout", timeout_ms)

    # Port columns.
    P = {n: z3.Int(f"P_{n}") for n in names}
    if free_ports:
        for n in names:
            opt.add(P[n] >= pmin, P[n] <= wmax)
        # Keep the current relative order within each direction group; bands
        # are then the midpoint Voronoi cells of adjacent same-group ports.
        for grp in set(p[1] for p in ports.values()):
            cols = [n for n in names if ports[n][1] == grp]
            cols.sort(key=lambda n: ports[n][0])
            for a, b in zip(cols, cols[1:]):
                opt.add(P[b] >= P[a] + min_sep)
    if free_ports and snake_geometry:
        # Component geometry (compact floor, code-relative): scratch needs
        # sp>=6+3; scalar command jog: rp west of the sc->27 jog, sc east of it;
        # rr reply turn exits at col 31; sd's vertical must clear that run;
        # display is pinned at dx = sa-8 between scalar (ends 55) and cell
        # (starts 112); ss wraps around the display's east wall; cc jogs to
        # the cell command at 115; cr turns at 119.
        opt.add(P["ri"] >= 5, P["sp"] >= P["ri"] + 3, P["rp"] >= P["sp"] + 5)
        opt.add(P["rp"] <= 26, P["sc"] >= 28, P["rr"] >= 33)
        opt.add(P["sd"] >= P["rr"] + 2)
        opt.add(P["sa"] >= 66, P["sa"] <= 92)          # 58 <= dx=sa-8 <= 84
        opt.add(P["sd"] <= P["sa"] - 10)               # sd vertical west of dx-1
        opt.add(P["ss"] >= P["sa"] + 11)               # east of display wall+1
        opt.add(P["cc"] >= P["ss"] + 2, P["cc"] <= 113)
        opt.add(P["cr"] >= 121)
    if not free_ports:
        for n in names:
            opt.add(P[n] == ports[n][0])

    def band(op_c, name):
        """op at op_c binds to `name`: strictly nearest among its group."""
        grp = ports[name][1]
        cons = []
        for other in names:
            if other == name or ports[other][1] != grp:
                continue
            if ports[other][0] < ports[name][0]:
                cons.append(2 * op_c >= P[other] + P[name] + 2)
            else:
                cons.append(2 * op_c <= P[other] + P[name] - 2)
        return z3.And(cons)

    total_rows = []
    width_terms = []
    for label, seq in block_sequences(flow):
        ops = [(k, rest) for k, *rest in seq if k != "term"]
        term = next((rest[0] for k, *rest in seq if k == "term"), None)
        n = len(ops)
        if n == 0:
            continue
        r = [z3.Int(f"r_{label}_{i}") for i in range(n)]
        c = [z3.Int(f"c_{label}_{i}") for i in range(n)]
        e = [z3.Bool(f"e_{label}_{i}") for i in range(n)]
        opt.add(r[0] == 0, e[0])
        for i in range(n):
            opt.add(c[i] >= 1, c[i] <= wmax)
            width_terms.append(c[i])
            kind, rest = ops[i]
            if kind == "port":
                opt.add(band(c[i], rest[0]))
        for i in range(n - 1):
            opt.add(r[i + 1] >= r[i], r[i + 1] <= r[i] + 2)
            same = r[i + 1] == r[i]
            step1 = r[i + 1] == r[i] + 1
            opt.add(e[i + 1] == z3.If(step1, z3.Not(e[i]), e[i]))
            opt.add(z3.Implies(z3.And(same, e[i]), c[i + 1] >= c[i] + 1))
            opt.add(z3.Implies(z3.And(same, z3.Not(e[i])), c[i + 1] <= c[i] - 1))
            opt.add(z3.Implies(z3.And(step1, e[i]), c[i + 1] <= c[i]))
            opt.add(z3.Implies(z3.And(step1, z3.Not(e[i])), c[i + 1] >= c[i]))
        rows_b = z3.Int(f"rows_{label}")
        opt.add(rows_b == r[n - 1] + 1 + (1 if term == "br" else 0))
        total_rows.append(rows_b)

    T = z3.Int("T")
    opt.add(T == z3.Sum(total_rows))
    W = z3.Int("W")
    for t in width_terms:
        opt.add(W >= t)
    h1 = opt.minimize(T)
    opt.minimize(W)
    res = opt.check()
    if res != z3.sat:
        return None
    m = opt.model()
    return {
        "rows": m.eval(T).as_long(),
        "width": m.eval(W).as_long(),
        "ports": {n: m.eval(P[n]).as_long() for n in names},
    }


def greedy_rows(flow):
    """Count op rows the current greedy boustrophedon produces (same model:
    op rows + 1 per br, excluding merge bands and gaps)."""
    ports = flow.ports
    total = 0
    for label, seq in block_sequences(flow):
        x, heading, rows = 1, 1, 1
        term = None
        for k, *rest in seq:
            if k == "term":
                term = rest[0]
                break
            if k == "port":
                lo, hi = ports[rest[0]][2], ports[rest[0]][3]
                if heading == 1 and x > hi:
                    rows += 1
                    heading = -1
                    x -= 1
                if heading == -1 and x < lo:
                    rows += 1
                    heading = 1
                    x += 1
                x = max(x, lo) if heading == 1 else min(x, hi)
                x += heading
            else:
                if heading == -1 and x <= 0:
                    rows += 1
                    heading = 1
                    x += 1
                x += heading
        total += rows + (1 if term == "br" else 0)
    return total


def _block_ops(flow):
    for label, seq in block_sequences(flow):
        ops = [(k, rest) for k, *rest in seq if k != "term"]
        term = next((rest[0] for k, *rest in seq if k == "term"), None)
        yield label, ops, (1 if term == "br" else 0)


def _bands(flow, ops, wmax):
    ports = flow.ports
    out = []
    for kind, rest in ops:
        if kind == "port":
            lo, hi = ports[rest[0]][2], ports[rest[0]][3]
            out.append((max(1, lo), min(wmax, hi)))
        else:
            out.append((1, wmax))
    return out


def dp_block_rows(flow, ops, wmax):
    """Exact minimum rows for ONE block with the ports fixed — the same automaton smtrows
    encodes, solved as a shortest path instead of an ILP.

    State after op i is (heading, column); the three legal moves are the model's own:
      same row   -> strictly monotone column in the heading (0 rows)
      next row   -> heading flips, column may not overshoot the drop column (1 row)
      +2 rows    -> heading unchanged, column free (2 rows)
    94 states x 270 ops closes instantly, where Optimize() over the 52-op block did not
    close in 300s. Z3 then re-checks the answer (see `certify`), so the fast path is not
    trusted on its own."""
    bands = _bands(flow, ops, wmax)
    INF = float("inf")
    lo0, hi0 = bands[0]
    # heading 1 = east, -1 = west; blocks enter east on row 0.
    cur = {(1, c): 0 for c in range(lo0, hi0 + 1)}
    if not cur:
        return None
    for i in range(1, len(ops)):
        lo, hi = bands[i]
        nxt = {}
        # Precompute, per heading, the best cost reachable for each column.
        for (h, c), cost in cur.items():
            for c2 in range(lo, hi + 1):
                if h == 1 and c2 > c:
                    add, h2 = 0, 1
                elif h == -1 and c2 < c:
                    add, h2 = 0, -1
                elif h == 1 and c2 <= c:
                    add, h2 = 1, -1
                elif h == -1 and c2 >= c:
                    add, h2 = 1, 1
                else:
                    continue
                k = (h2, c2)
                if nxt.get(k, INF) > cost + add:
                    nxt[k] = cost + add
                # the +2 wrap keeps the heading and frees the column
                k2 = (h, c2)
                if nxt.get(k2, INF) > cost + 2:
                    nxt[k2] = cost + 2
        if not nxt:
            return None
        cur = nxt
    return min(cur.values()) + 1


def dp_fixed(flow, wmax):
    total, per_block = 0, {}
    for label, ops, extra in _block_ops(flow):
        if not ops:
            per_block[label] = 1 + extra
            total += 1 + extra
            continue
        r = dp_block_rows(flow, ops, wmax)
        if r is None:
            return None, label
        per_block[label] = r + extra
        total += r + extra
    return {"rows": total, "per_block": per_block}, None


def certify(flow, wmax, per_block, timeout_ms=120000):
    """Z3 optimality certificate for the DP answer: for each block assert `rows <= k-1`
    and require UNSAT, then assert `rows <= k` and require SAT. A plain satisfiability
    query, not an optimisation — that is what makes it close where Optimize() did not."""
    ports = flow.ports
    bad = []
    for label, ops, extra in _block_ops(flow):
        if not ops:
            continue
        k = per_block[label] - extra
        n = len(ops)

        def feasible(limit):
            s = z3.Solver()
            s.set("timeout", timeout_ms)
            r = [z3.Int(f"r{i}") for i in range(n)]
            c = [z3.Int(f"c{i}") for i in range(n)]
            e = [z3.Bool(f"e{i}") for i in range(n)]
            s.add(r[0] == 0, e[0])
            for i in range(n):
                lo, hi = _bands(flow, ops, wmax)[i]
                s.add(c[i] >= lo, c[i] <= hi)
                s.add(r[i] >= 0, r[i] <= limit - 1)
            for i in range(n - 1):
                s.add(r[i + 1] >= r[i], r[i + 1] <= r[i] + 2)
                same = r[i + 1] == r[i]
                step1 = r[i + 1] == r[i] + 1
                s.add(e[i + 1] == z3.If(step1, z3.Not(e[i]), e[i]))
                s.add(z3.Implies(z3.And(same, e[i]), c[i + 1] >= c[i] + 1))
                s.add(z3.Implies(z3.And(same, z3.Not(e[i])), c[i + 1] <= c[i] - 1))
                s.add(z3.Implies(z3.And(step1, e[i]), c[i + 1] <= c[i]))
                s.add(z3.Implies(z3.And(step1, z3.Not(e[i])), c[i + 1] >= c[i]))
            return s.check()

        if feasible(k) != z3.sat:
            bad.append((label, k, "claimed bound not SAT"))
            continue
        if k > 1 and feasible(k - 1) != z3.unsat:
            bad.append((label, k, "k-1 not proven UNSAT"))
    return bad


def solve_fixed(flow, wmax=155, timeout_ms=60000, verbose=False):
    """Phase 1 (ports FIXED), solved BLOCK BY BLOCK.

    With the port columns pinned, no constraint couples two blocks — each block's rows depend
    only on its own op sequence and the fixed bands — so the joint optimum is exactly the sum
    of the per-block optima. The monolithic Optimize() over all blocks at once did not close
    in 300s on the snake lift (25 blocks, 270 ops); decomposed it is 25 tiny problems and
    finishes in seconds, and the answer is the same number."""
    ports = flow.ports
    names = list(ports)
    total, width, per_block = 0, 0, {}
    for label, seq in block_sequences(flow):
        ops = [(k, rest) for k, *rest in seq if k != "term"]
        term = next((rest[0] for k, *rest in seq if k == "term"), None)
        n = len(ops)
        extra = 1 if term == "br" else 0
        if n == 0:
            total += 1 + extra
            per_block[label] = (1 + extra, 0)
            continue
        opt = z3.Optimize()
        opt.set("timeout", timeout_ms)
        r = [z3.Int(f"r{i}") for i in range(n)]
        c = [z3.Int(f"c{i}") for i in range(n)]
        e = [z3.Bool(f"e{i}") for i in range(n)]
        opt.add(r[0] == 0, e[0])
        for i in range(n):
            opt.add(c[i] >= 1, c[i] <= wmax)
            kind, rest = ops[i]
            if kind == "port":
                lo, hi = ports[rest[0]][2], ports[rest[0]][3]
                opt.add(c[i] >= lo, c[i] <= hi)
        for i in range(n - 1):
            opt.add(r[i + 1] >= r[i], r[i + 1] <= r[i] + 2)
            same = r[i + 1] == r[i]
            step1 = r[i + 1] == r[i] + 1
            opt.add(e[i + 1] == z3.If(step1, z3.Not(e[i]), e[i]))
            opt.add(z3.Implies(z3.And(same, e[i]), c[i + 1] >= c[i] + 1))
            opt.add(z3.Implies(z3.And(same, z3.Not(e[i])), c[i + 1] <= c[i] - 1))
            opt.add(z3.Implies(z3.And(step1, e[i]), c[i + 1] <= c[i]))
            opt.add(z3.Implies(z3.And(step1, z3.Not(e[i])), c[i + 1] >= c[i]))
        W = z3.Int("W")
        for i in range(n):
            opt.add(W >= c[i])
        opt.minimize(r[n - 1])
        opt.minimize(W)
        if opt.check() != z3.sat:
            return None
        m = opt.model()
        rows = m.eval(r[n - 1]).as_long() + 1 + extra
        w = m.eval(W).as_long()
        per_block[label] = (rows, w)
        total += rows
        width = max(width, w)
        if verbose:
            print(f"    {label:>4}: {n:>3} ops -> {rows} rows, width {w}")
    return {"rows": total, "width": width, "per_block": per_block,
            "ports": {n: ports[n][0] for n in names}}


def as_built_rows(flow):
    """The SAME accounting applied to the grid the flow was lifted from. Without this the
    Z3 number has nothing honest to be compared against — `greedy_rows` re-simulates
    flowgrid's greedy, which is not what a hand-structured champion did.

    Returns (block_rows, physical_rows). They differ, and the difference is the point:
      * block_rows counts each block's own distinct rows, which is the model's unit — the
        model lays blocks one under another and cannot let two share a row;
      * physical_rows is the number of grid rows that actually carry an op.
    A hand-folded champion parks several small blocks on one row, so physical_rows can be
    BELOW the model's optimum. No `br` surcharge is added here: flowgrid emits `v` then `X`
    on the next row (hence the model's +1 per br), but the lifted grid puts `X` inline on a
    row already counted, so adding it again would invent rows the champion does not spend."""
    cells = getattr(flow, "meta", {}).get("block_cells")
    if not cells:
        return None, None
    total, phys = 0, set()
    for label in flow.blocks:
        rows = {y for (_, y) in cells.get(label, ())}
        phys |= rows
        total += max(len(rows), 1)
    return total, len(phys)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="build*.py exposing build_flow(), or any .man grid")
    ap.add_argument("--free-ports", action="store_true")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--man-index", type=int, default=None,
                    help=".man input: which man's room to model (default: most ops)")
    ap.add_argument("--trace", metavar="SLUG",
                    help=".man input: intersect the lift with cells the engine really ran")
    ap.add_argument("--wmax", type=int, default=None)
    ap.add_argument("--min-sep", type=int, default=4)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-certify", action="store_true")
    args = ap.parse_args()
    flow = load_flow(args.source, man_index=args.man_index, trace=args.trace)
    wmax = args.wmax
    if wmax is None:
        interior = getattr(flow, "meta", {}).get("room_interior")
        wmax = (interior[2] - interior[0] + 1) if interior else 155
    ab, phys = as_built_rows(flow)
    if ab is not None:
        print(f"as-built: {ab} block-rows, {phys} PHYSICAL op rows "
              f"({ab - phys} shared between blocks — a fold the model cannot express)")
    print(f"greedy op rows (current ports): {greedy_rows(flow)}")
    nbr = sum(1 for toks in flow.blocks.values()
              if toks and isinstance(toks[-1], tuple) and toks[-1][0] == "br")
    import time
    t0 = time.time()
    if args.free_ports:
        r = solve(flow, free_ports=True, timeout_ms=args.timeout * 1000,
                  wmax=wmax, min_sep=args.min_sep,
                  pmin=1 if not (flow.ports is stateflow.COMPACT_PORTS) else 4)
    else:
        r, bad_label = dp_fixed(flow, wmax)
        if r is None:
            print(f"solver: block {bad_label} has no legal placement at wmax={wmax}")
            sys.exit(1)
        if args.verbose:
            for lbl, k in r["per_block"].items():
                print(f"    {lbl:>4}: {k} rows")
        if not args.no_certify:
            t1 = time.time()
            bad = certify(flow, wmax, r["per_block"], timeout_ms=args.timeout * 1000)
            print(f"z3 certificate: {'OK (each block proven optimal)' if not bad else bad}"
                  f"  [{time.time() - t1:.1f}s]")
        r.setdefault("width", wmax)
    dt = time.time() - t0
    if r is None:
        print(f"solver: UNSAT/timeout after {dt:.1f}s")
    else:
        print(f"smt op rows: {r['rows']}  width: {r['width']}  (wmax {wmax}, {dt:.1f}s)")
        print(f"  of which {nbr} are the flowgrid `br` surcharge (one row per branch); a grid"
              f" that puts `X` inline needs only {r['rows'] - nbr}")
        if ab is not None:
            print(f"  vs as-built {ab} block-rows / {phys} physical rows")
        if args.free_ports:
            print("ports:", {k: v for k, v in sorted(r["ports"].items(), key=lambda kv: kv[1])})
