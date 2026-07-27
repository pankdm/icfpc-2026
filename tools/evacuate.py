#!/usr/bin/env python3
"""evacuate.py — EVACUATE A LINE: the move that turns freed space into a DELETED LINE.

WHY THIS MOVE EXISTS.  `score = max(w,h)^2 * avgTicks`, and the law that governs every
geometric pass in this repo is that **a HOLE does not shrink max(w,h)**.  The
superoptimizer frees cells, `place.py` slides rooms, `smtrows` compacts ops — and all of
it is worth exactly zero unless the freed cells line up into a whole blank row or column
ON THE BINDING AXIS.  This pass aims at that directly: pick a line, push everything off
it, delete it, and let the far side fall in by one.

WHAT THE MOVE ACTUALLY IS.  "Evacuate row y" is NOT "erase row y".  Erasing leaves an
empty interior row, and an empty interior row still sits inside the bounding box, so the
score does not move.  The move is:

    every block whose rect lies strictly BELOW y moves up by one (rigidly, with its man
    and all of his code), every block above stays put, and EVERY PIPE IS RE-ROUTED AT ITS
    EXACT ORIGINAL LENGTH in the one-row-shorter box.

Rigid blocks are what makes it safe: a man's tick count is the number of cells he walks,
and none of his cells move relative to each other.  Exact-length pipes are what makes it
PROVABLE: a pipe's length is its latency and its capacity, so preserving it exactly means
`tools/equiv.py` certifies the result without a single tick of simulation.

THE THREE PRECONDITIONS, and why each is a hard gate rather than a heuristic:

  1. NO BLOCK MAY STRADDLE THE LINE.  A room is rigid — it cannot lose a row.  Since a
     room's border spans its full rect on every row it occupies, "no block straddles"
     is exactly "every non-space cell on the line is a PIPE cell".

  2. NO PIPE MAY SPAN THE LINE (`shear=0`).  This one is a THEOREM, not a routing
     difficulty.  A pipe from a block above to a block below has its two border
     endpoints move 1 closer in Manhattan distance when the far side falls in, and
     `router.pipe_len_parity` says every legal pipe between two fixed border points has
     a FIXED length parity — so the original length becomes unreachable.  Not "hard to
     route": unreachable.  Shortening is forbidden (capacity + latency), so the move
     fails cleanly with reason `pipe-spans-line`.

     `--shear +1|-1` is the escape hatch: displacing the far side by one cell ALONG the
     line at the same time restores the parity (Manhattan changes by 0 or 2), at the
     price of one cell on the non-binding axis — which is free whenever that axis has
     slack, i.e. whenever `w < h` for a row deletion.

  3. THE BINDING MUST NOT MOVE.  Measured on Grade Book: a 47x58 floorplan routed
     PERFECTLY at exact length and `build()` still rejected it with "nearest-pipe
     resolution changed".  Routing was never the blocker; `r`/`s`/`q` binding is.  So
     every candidate goes through `place.Plan.build` (nearest-pipe under BOTH endpoint
     readings, R/U reading-order permutation, adjacency guard, glyph collision) and then
     `place.verify_topology` (re-parse with the real lifter).  A re-route only changes
     binding if it moves path[0] or path[-1]; a mid-path detour does not.

  python3 tools/evacuate.py <file.man> --scan                 # what is evacuable, and why not
  python3 tools/evacuate.py <file.man> --axis row --line 74 -o out.man
  python3 tools/evacuate.py <file.man> --all -o out.man       # fixpoint on the binding axis
  python3 tools/evacuate.py <file.man> --all --shear auto -o out.man
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import place as P  # noqa: E402  (repo tool, path set above)

LM = REPO / "interp" / "target" / "release" / "lm"


# ══════════════════════════════════════════════════════ the engine as the gate
# MEASURED, and it is the whole reason this section exists: an 8-row evacuation of matmul
# passed `place.Plan.build` (nearest-pipe both readings, R/U order, glyph collision), passed
# `place.verify_topology` (which re-parses with `tools/lift.py` and counted 12 pipes), and
# was CERTIFIED EQUIVALENT by `tools/equiv.py` — and then graded 0/7 with
# `loaderror: input room has multiple pipes`.  The engine parses that grid as **15** pipes,
# not 12: a re-routed pipe's arrowhead landing beside a room border is read as a SECOND
# pipe start, and neither the model-level checks nor lift.py can see it.
#
# So the gate is the engine.  `lm <file> 0` loads the grid and prints one JSON snapshot in
# milliseconds, and it reports each pipe's FIRST and LAST CELL — so we can compare its parse
# against the exact path set we drew, cell for cell.  Do not replace this with a Python
# re-implementation of pipe parsing: the disagreement above is precisely what that would
# reproduce.
#
# And it is not only a gate, it is a REPAIR SIGNAL.  An extra pipe's reported `src` IS the
# offending arrowhead, so `evacuate_line` forbids that cell and re-routes, up to `repairs`
# times.  On matmul that turns "28 lines rejected: input room has multiple pipes" into real
# evacuations — rejecting alone got 1 row, repairing gets more.


def engine_parse(path):
    """(loaderror or None, [(first_cell, last_cell)]) as the RUST ENGINE parses `path`."""
    if not LM.exists():
        raise SystemExit("interp/target/release/lm not built — "
                         "cargo build --release --manifest-path interp/Cargo.toml")
    r = subprocess.run([str(LM), str(path), "0"], capture_output=True, text=True)
    snap = None
    for line in (r.stdout or "").splitlines():
        if line.startswith("{"):
            snap = json.loads(line)
            break
    if snap is None:
        return (r.stderr or "engine produced no snapshot").strip()[:160], []
    ends = [(tuple(p["src"]), tuple(p["dst"])) for p in (snap.get("pipes") or [])]
    return snap.get("loaderror"), ends


def engine_parse_text(text):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".man", delete=False)
    try:
        tmp.write(text)
        tmp.close()
        return engine_parse(tmp.name)
    finally:
        os.unlink(tmp.name)


def engine_check(text, expected_ends):
    """Compare the engine's parse of `text` against the (first,last) cells we DREW.

    Returns (reason or None, offending_cells) — the offenders are the first cells of the
    pipes the engine invented, which is exactly the set to forbid and re-route around."""
    err, got = engine_parse_text(text)
    if err:
        # a loaderror still comes with the pipe list it managed to build, so the extra
        # starts are visible even when the load was refused
        extra = [a for (a, b) in got if (a, b) not in expected_ends]
        return f"engine loaderror: {err}", extra
    want = list(expected_ends)
    extra = []
    for e in got:
        if e in want:
            want.remove(e)
        else:
            extra.append(e[0])
    if extra or want:
        return (f"engine parses {len(got)} pipes, we drew {len(expected_ends)}: "
                f"{len(extra)} invented, {len(want)} missing"), extra
    return None, []


# ═══════════════════════════════════════════════════════════════════ geometry


def grid_bbox(rows):
    """(minx, miny, maxx, maxy) of the non-space cells — the scored footprint."""
    ys = [y for y, r in enumerate(rows) if r.strip()]
    if not ys:
        return (0, 0, -1, -1)
    w = max(len(r) for r in rows)
    xs = [x for x in range(w) if any(len(r) > x and r[x] != " " for r in rows)]
    return (xs[0], ys[0], xs[-1], ys[-1])


def _axis_i(axis):
    """0 for a column (x is the deleted coordinate), 1 for a row (y is)."""
    if axis not in ("row", "col"):
        raise ValueError(f"axis must be 'row' or 'col', got {axis!r}")
    return 1 if axis == "row" else 0


LineReport = namedtuple(
    "LineReport",
    "axis index verdict blocks orphans pipes spanning")


def scan_lines(plan, axis):
    """Diagnose every line of `plan` on `axis`.

    verdict is one of:
      "candidate"  — nothing but pipe cells, and no pipe spans it (shear-free legal)
      "shearable"  — nothing but pipe cells, but some pipe spans it (needs --shear +-1)
      "block"      — a room/display rect covers it; a rigid block cannot lose a line
      "orphan"     — a stray glyph belonging to no block and no pipe sits on it
    """
    ax = _axis_i(axis)
    x0, y0, x1, y1 = grid_bbox(plan.rows)
    lo, hi = (y0, y1) if ax else (x0, x1)

    block_span = []                       # (bi, lo, hi) on the deleted axis
    for bi, b in enumerate(plan.blocks):
        r = b.rect(b.ox0, b.oy0)
        block_span.append((bi, r[ax], r[ax + 2]))
    orphan_at = {}
    for c in plan.orphans:
        orphan_at.setdefault(c[ax], []).append(c)
    pipe_at = {}
    for p in plan.pipes:
        for c in p.cells:
            pipe_at.setdefault(c[ax], set()).add(p.idx)

    out = []
    for idx in range(lo, hi + 1):
        hit = [bi for bi, a, b_ in block_span if a <= idx <= b_]
        orph = orphan_at.get(idx, [])
        pipes = sorted(pipe_at.get(idx, ()))
        spanning = sorted(p.idx for p in plan.pipes if _spans(plan, p, ax, idx))
        if hit:
            v = "block"
        elif orph:
            v = "orphan"
        elif spanning:
            v = "shearable"
        else:
            v = "candidate"
        out.append(LineReport(axis, idx, v, hit, orph, pipes, spanning))
    return out


def _side(plan, bi, ax, idx):
    """-1 if block `bi` lies entirely before the line, +1 if entirely after."""
    b = plan.blocks[bi]
    r = b.rect(b.ox0, b.oy0)
    return -1 if r[ax + 2] < idx else 1


def _spans(plan, p, ax, idx):
    """Does pipe `p` connect a block before the line to a block after it?

    That is the parity killer: the two border endpoints move 1 closer, and
    `router.pipe_len_parity` fixes the length parity of every legal route between them,
    so the original length becomes unreachable."""
    return _side(plan, p.src_b, ax, idx) != _side(plan, p.dst_b, ax, idx)


# ═══════════════════════════════════════════════════════════════════ the move


def _reuse_first_order(plan, layout, routing_bound, orphans, forbid=()):
    """Route the pipes that DO NOT have to move first, then the movers, longest-first.

    `place.py`'s default order is longest-first, which is right when every pipe is being
    re-derived.  Here almost nothing moves: a line evacuation displaces one side rigidly,
    so most pipes translate onto their own old cells and only the few that touched the
    line (or that left the shrunk box) need a new path.  Routing a 116-cell mover BEFORE
    a 334-cell pipe that was never going to move lets the mover eat the other's lane and
    reports the wrong net as unroutable — measured on matmul row 0.  So: freeze the
    survivors, then squeeze the movers into what is left."""
    offsets = layout[0]
    occ = set(orphans) | set(forbid)
    for b, (ox, oy) in zip(plan.blocks, offsets):
        x0, y0, x1, y1 = b.rect(ox, oy)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                occ.add((x, y))
    keep, move = [], []
    taken = set()
    for p in plan.pipes:
        src, dst = plan.ends(layout, p)
        r = plan._reuse(p, src, dst, occ, taken, routing_bound)
        if r is None:
            move.append(p.idx)
        else:
            keep.append(p.idx)
            taken |= set(r[0])
    move.sort(key=lambda i: -plan.pipes[i].length)
    order = keep + move

    def _order(layout_, pipe_len, pipe_modes=None):
        return order
    return _order


class EvacResult:
    """Falsy on failure, carrying WHY.

    reason ∈ {"out-of-range", "block-straddles-line", "orphan-on-line",
              "pipe-spans-line", "unroutable", "pipe grazes a room wall",
              "nearest-pipe resolution changed", "glyph collision",
              "blocks overlap", "topology:<detail>", "box-did-not-shrink"}"""

    def __init__(self, ok, reason="", text=None, before=None, after=None,
                 layout=None, paths=None, moved=()):
        self.ok = ok
        self.reason = reason
        self.text = text
        self.before = before          # (w, h, box)
        self.after = after
        self.layout = layout
        self.paths = paths
        self.moved = tuple(moved)     # block indices that fell in

    def __bool__(self):
        return bool(self.ok)

    def __repr__(self):
        if self.ok:
            return (f"EvacResult(ok, {self.before[0]}x{self.before[1]} -> "
                    f"{self.after[0]}x{self.after[1]}, box {self.before[2]:,} -> "
                    f"{self.after[2]:,})")
        return f"EvacResult(FAILED, {self.reason!r})"


def evacuate_line(plan, axis, index, shear=0, pipe_len="exact", slack=None,
                  margin=8, allow_grow=True, engine=True, route_guard=False,
                  repairs=6):
    """Delete line `index` on `axis` from `plan`, re-routing every pipe off it.

    plan       : a `place.Plan` (rigid blocks + lifted pipes + the four cliff checks)
    axis       : "row" (delete a y) or "col" (delete an x)
    index      : the grid coordinate of the line to delete
    shear      : perpendicular displacement applied to the FAR side together with the
                 fall-in.  0 keeps every endpoint pair at a fixed Manhattan distance
                 (equiv-provable); +-1 restores parity for pipes that SPAN the line, at
                 the cost of one cell on the non-binding axis.
    pipe_len   : "exact" (default; capacity and latency preserved, equiv-provable),
                 "min" (a floor only) or "free" (anything — NOT provable).
    slack      : how far the perpendicular axis may grow.  None = up to the new binding
                 side, which is FREE (max(w,h) does not see it).  0 = not at all.
    allow_grow : if False, reject a result whose box is not strictly smaller.
    engine     : gate the result with the RUST ENGINE's own parse (see engine_check).
                 Not optional in practice — it is the only check that caught matmul's
                 15-pipes-instead-of-12 re-parse, which every model-level check passed.
    repairs    : how many times to forbid the cells the engine read as invented pipe
                 starts and re-route.  0 makes the engine a pure gate.

    Returns an EvacResult.  The input plan is never modified (orphans are restored).
    """
    ax = _axis_i(axis)
    px = 1 - ax                                   # the perpendicular axis
    x0, y0, x1, y1 = grid_bbox(plan.rows)
    lo, hi = (y0, y1) if ax else (x0, x1)
    plo, phi = (x0, x1) if ax else (y0, y1)
    w0, h0 = x1 - x0 + 1, y1 - y0 + 1
    before = (w0, h0, max(w0, h0) ** 2)

    if not (lo <= index <= hi):
        return EvacResult(False, "out-of-range", before=before)

    rep = [r for r in scan_lines(plan, axis) if r.index == index][0]
    if rep.verdict == "block":
        return EvacResult(False, f"block-straddles-line (blocks {rep.blocks})",
                          before=before)
    if rep.verdict == "orphan":
        return EvacResult(False, f"orphan-on-line ({rep.orphans[:4]})", before=before)
    if rep.spanning and shear == 0:
        return EvacResult(
            False,
            f"pipe-spans-line (pipes {rep.spanning}): the far side falls in by one, so "
            f"each of those pipes' endpoints move 1 closer and its length PARITY flips "
            f"— the original length is unreachable, not merely hard to route.  "
            f"Try --shear +1 / -1.",
            before=before)

    # ── the new floorplan: everything after the line falls in by one (+ shear) ──
    delta = [0, 0]
    delta[ax] = -1
    delta[px] = shear
    moved = []
    offs = []
    for bi, b in enumerate(plan.blocks):
        if _side(plan, bi, ax, index) > 0:
            offs.append((b.ox0 + delta[0], b.oy0 + delta[1]))
            moved.append(bi)
        else:
            offs.append((b.ox0, b.oy0))
    layout = (tuple(offs), tuple((p.src_off, p.dst_off) for p in plan.pipes))

    orphans = {}
    for (ox, oy), ch in plan.orphans.items():
        if (oy if ax else ox) > index:
            orphans[(ox + delta[0], oy + delta[1])] = ch
        else:
            orphans[(ox, oy)] = ch

    # ── the routing box.  The deleted axis is pinned one shorter; the perpendicular
    # axis may grow up to the new binding side FOR FREE (max(w,h) cannot see it). ──
    new_len = (hi - lo + 1) - 1
    pneed = phi - plo + 1 + (1 if shear else 0)
    if slack is None:
        pmax = max(pneed, new_len)
    else:
        pmax = pneed + slack
    plo2 = plo + min(0, shear)
    bnd = [0, 0, 0, 0]
    bnd[ax], bnd[ax + 2] = lo, lo + new_len - 1
    bnd[px], bnd[px + 2] = plo2, plo2 + pmax - 1
    routing_bound = tuple(bnd)

    # A pipe's first/last cell must be an orthogonal neighbour of its border cell that is
    # not inside a block and not off the new box.  When the attach faces the line being
    # deleted (matmul's pipe 8 enters block 8 through its BOTTOM wall, on the grid's last
    # row) there is no such cell at all, and "pipe N unroutable" would hide the fact that
    # the only fix is to MOVE THE PORT — which re-binds.
    occ0 = set(orphans)
    for b, (ox, oy) in zip(plan.blocks, offs):
        bx0, by0, bx1, by1 = b.rect(ox, oy)
        for yy in range(by0, by1 + 1):
            for xx in range(bx0, bx1 + 1):
                occ0.add((xx, yy))
    for p in plan.pipes:
        for end, tag in zip(plan.ends(layout, p), ("src", "dst")):
            free = [(end[0] + dx, end[1] + dy) for dx, dy in P.DIRS4
                    if (end[0] + dx, end[1] + dy) not in occ0
                    and routing_bound[0] <= end[0] + dx <= routing_bound[2]
                    and routing_bound[1] <= end[1] + dy <= routing_bound[3]]
            if not free:
                return EvacResult(
                    False,
                    f"endpoint-boxed-in (pipe {p.idx} {tag} at {end}): its attach faces "
                    f"the deleted line, so no first/last cell exists inside the shrunk "
                    f"box.  Only moving the PORT can fix this, and that re-binds.",
                    before=before, layout=layout, moved=moved)

    forbid = set()
    fail = None
    for _attempt in range(repairs + 1):
        saved = plan.orphans
        saved_order = plan.__dict__.get("_default_order")
        saved_guard = getattr(plan, "route_guard", False)
        saved_occ = plan.__dict__.get("occupancy")
        plan.orphans = orphans
        # forbidding a cell = making the router see it as occupied.  It must NOT become a
        # glyph, so this shadows `occupancy` (routing only) rather than adding an orphan.
        if forbid:
            base_occ = P.Plan.occupancy
            plan.occupancy = (lambda offsets, _p=plan, _f=frozenset(forbid):
                              base_occ(_p, offsets) | _f)
        plan._default_order = _reuse_first_order(plan, layout, routing_bound, orphans,
                                                 forbid)
        # route_guard protects EVERY room border against NEW routes even when the champion
        # itself grazes walls.  It is a FALLBACK, not a default: on matmul (whose champion
        # grazes everywhere) turning it on makes every single line unroutable, so the
        # engine gate below is the decider and this is the second thing to try.
        plan.route_guard = route_guard
        try:
            cells, err, paths = plan.build(layout, pipe_len=pipe_len, margin=margin,
                                           routing_bound=routing_bound)
        finally:
            plan.orphans = saved
            plan.route_guard = saved_guard
            for name, val in (("_default_order", saved_order), ("occupancy", saved_occ)):
                if val is None:
                    plan.__dict__.pop(name, None)
                else:
                    plan.__dict__[name] = val
        if cells is None:
            return EvacResult(False, err if not forbid else f"{err} (after {len(forbid)} "
                              f"cells forbidden to kill invented pipe starts)",
                              before=before, layout=layout, moved=moved)

        saved = plan.orphans
        plan.orphans = orphans
        try:
            why = P.verify_topology(plan, cells, layout)
        finally:
            plan.orphans = saved
        if why:
            return EvacResult(False, f"topology:{why}", before=before, layout=layout,
                              moved=moved)

        w, h, box = P.box_of(cells)
        after = (w, h, box)
        if not allow_grow and box >= before[2]:
            return EvacResult(False, f"box-did-not-shrink ({before[2]:,} -> {box:,})",
                              before=before, after=after, layout=layout, moved=moved)
        text = P.render(P.trimmed(cells))
        if not engine:
            return EvacResult(True, "", text=text, before=before, after=after,
                              layout=layout, paths=paths, moved=moved)

        # the engine reads the TRIMMED grid, so compare in trimmed coordinates
        mx = min(x for x, _ in cells)
        my = min(y for _, y in cells)
        expect = [((c[0][0] - mx, c[0][1] - my), (c[-1][0] - mx, c[-1][1] - my))
                  for c, _d in paths]
        why, extra = engine_check(text, expect)
        if why is None:
            return EvacResult(True, "", text=text, before=before, after=after,
                              layout=layout, paths=paths, moved=moved)
        fail = EvacResult(False, f"engine:{why}", before=before, after=after,
                          layout=layout, moved=moved)
        new = {(c[0] + mx, c[1] + my) for c in extra} - forbid
        if not new:
            break                       # nothing left to forbid — this line is a dead end
        forbid |= new
    return fail


# ═══════════════════════════════════════════════════════════════ driver / CLI


def binding_axis(rows):
    """Which axis the score squares: "col" when width >= height (deleting a column is
    what shrinks max(w,h)), "row" otherwise."""
    x0, y0, x1, y1 = grid_bbox(rows)
    return "col" if (x1 - x0) >= (y1 - y0) else "row"


def evacuate_all(path, axis=None, shear_modes=(0,), pipe_len="exact", slack=None,
                 margin=8, verbose=False, max_rounds=200):
    """Fixpoint: repeatedly evacuate one line of the binding axis until nothing works.

    After every success the grid is re-lifted from scratch, because deleting a line
    changes which lines are pipe-only AND which pipes span what."""
    text = Path(path).read_text(encoding="utf-8")
    log = []
    tmp = tempfile.NamedTemporaryFile("w", suffix=".man", delete=False)
    tmp.close()
    cur = Path(tmp.name)
    cur.write_text(text, encoding="utf-8")
    total = None
    try:
        for _ in range(max_rounds):
            plan = P.Plan(cur)
            ax = axis or binding_axis(plan.rows)
            if total is None:
                x0, y0, x1, y1 = grid_bbox(plan.rows)
                total = (x1 - x0 + 1, y1 - y0 + 1)
            reps = scan_lines(plan, ax)
            got = None
            for sh in shear_modes:
                cands = [r for r in reps
                         if r.verdict == "candidate" or (sh and r.verdict == "shearable")]
                for r in cands:
                    for guard in (False, True):
                        res = evacuate_line(plan, ax, r.index, shear=sh,
                                            pipe_len=pipe_len, slack=slack,
                                            margin=margin, allow_grow=False,
                                            route_guard=guard)
                        if verbose:
                            tag = "OK " if res else "-- "
                            print(f"    {tag}{ax} {r.index} shear {sh:+d} guard {guard}: "
                                  f"{res.reason if not res else repr(res)}")
                        if res:
                            break
                        # only an engine re-parse is worth retrying under the guard;
                        # an unroutable net only gets harder with more constraints
                        if not res.reason.startswith("engine:"):
                            break
                    if res:
                        got = (r.index, sh, res)
                        break
                if got:
                    break
            if not got:
                break
            idx, sh, res = got
            cur.write_text(res.text, encoding="utf-8")
            log.append((ax, idx, sh, res.before, res.after))
            print(f"  evacuated {ax} {idx} (shear {sh:+d}): "
                  f"{res.before[0]}x{res.before[1]} -> {res.after[0]}x{res.after[1]}  "
                  f"box {res.before[2]:,} -> {res.after[2]:,}")
        out = cur.read_text(encoding="utf-8")
    finally:
        os.unlink(cur)
    return out, log


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("man")
    ap.add_argument("--scan", action="store_true",
                    help="report every line and why it is or is not evacuable")
    ap.add_argument("--axis", choices=("row", "col"), default=None)
    ap.add_argument("--line", type=int, default=None)
    ap.add_argument("--shear", default="0",
                    help="0 | +1 | -1 | auto (try 0, then -1, then +1)")
    ap.add_argument("--all", action="store_true", help="fixpoint on the binding axis")
    ap.add_argument("--pipe-len", choices=("exact", "min", "free"), default="exact")
    ap.add_argument("--slack", type=int, default=None,
                    help="how far the NON-binding axis may grow (default: free, up to "
                         "the new binding side)")
    ap.add_argument("--margin", type=int, default=8)
    ap.add_argument("--no-engine", action="store_true",
                    help="skip the Rust-engine re-parse gate (NOT recommended)")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    shear_modes = ((0, -1, 1) if args.shear == "auto" else (int(args.shear),))

    if args.scan:
        plan = P.Plan(args.man)
        x0, y0, x1, y1 = grid_bbox(plan.rows)
        w, h = x1 - x0 + 1, y1 - y0 + 1
        print(f"{os.path.basename(args.man)}  {w}x{h}  box {max(w,h)**2:,}  "
              f"blocks {len(plan.blocks)}  pipes {len(plan.pipes)}  "
              f"orphans {len(plan.orphans)}  binding axis: {binding_axis(plan.rows)}")
        for ax in ("row", "col"):
            reps = scan_lines(plan, ax)
            n = {}
            for r in reps:
                n[r.verdict] = n.get(r.verdict, 0) + 1
            print(f"  {ax}s {len(reps)}: " +
                  ", ".join(f"{k} {v}" for k, v in sorted(n.items())))
            for r in reps:
                if r.verdict in ("candidate", "shearable"):
                    print(f"    {ax} {r.index}: {r.verdict}  pipes_on_line={r.pipes}"
                          + (f"  spanning={r.spanning}" if r.spanning else ""))
        return

    if args.all:
        text, log = evacuate_all(args.man, axis=args.axis, shear_modes=shear_modes,
                                 pipe_len=args.pipe_len, slack=args.slack,
                                 margin=args.margin, verbose=args.verbose)
        if not log:
            print("no line could be evacuated")
            sys.exit(1)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"wrote {args.out}  ({len(log)} lines evacuated)")
        else:
            sys.stdout.write(text)
        return

    plan = P.Plan(args.man)
    ax = args.axis or binding_axis(plan.rows)
    if args.line is None:
        sys.exit("give --line N (or --scan / --all)")
    for sh in shear_modes:
        res = evacuate_line(plan, ax, args.line, shear=sh, pipe_len=args.pipe_len,
                            slack=args.slack, margin=args.margin, allow_grow=False)
        print(f"shear {sh:+d}: {res!r}")
        if res:
            if args.out:
                Path(args.out).write_text(res.text, encoding="utf-8")
                print(f"wrote {args.out}")
            else:
                sys.stdout.write(res.text)
            return
    sys.exit(1)


if __name__ == "__main__":
    main()
