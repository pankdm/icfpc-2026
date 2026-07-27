"""Unit tests for LENGTH-PRESERVING FOLDED ROUTING (tools/router.py).

Contract under test
-------------------
    route_pipe_len(grid, net, required, mode="exact")  ->  (cells, dirs) | FoldFailure
    fold_path(grid, cells, required, src, dst)         ->  cells        | FoldFailure

A pipe's LENGTH IS ITS CAPACITY AND LATENCY, so a re-route may never shorten it.  The
router therefore has to be able to PAD: route the shortest path, then absorb the slack
in an accordion serpentine placed in nearby FREE cells (each fold buys 2 cells of length
for 1 cell of width).

Every produced pipe is validated with the EXISTING validators:
  * layout.validate_pipe        (straight-ended pipes)
  * router.validate_pipe_oracle (also accepts the bent end the oracle accepts)
and additionally re-parsed by the real Rust engine in the end-to-end test.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))

import layout as L                                     # noqa: E402
import router as R                                     # noqa: E402
from router import (Grid, PipeNet, FREE, WALL, ROOM, PIPE, PLACED)   # noqa: E402

FAILS = []


def check(name, cond, msg=""):
    if cond:
        print(f"[ok] {name}")
    else:
        print(f"[FAIL] {name}: {msg}")
        FAILS.append(name)


def validate_both(cells, dirs, src, dst, occupied=()):
    """Validate with BOTH existing validators (never a new one)."""
    R.validate_pipe_oracle(cells, dirs, src, dst, occupied=occupied)
    # layout.validate_pipe only models a STRAIGHT end; use it whenever the end is straight
    endseg = R._unit(cells[-1][0] - cells[-2][0], cells[-1][1] - cells[-2][1])
    if endseg == dirs[-1]:
        L.validate_pipe(cells, src, dst, occupied=occupied)
    return True


def open_grid(w, h, wallcols=()):
    """A bare arena: two 3x3 rooms are added by the caller; everything else FREE."""
    g = Grid()
    for x in range(w):
        for y in range(h):
            g.typ[(x, y)] = FREE
    return g


def box_room(g, x0, y0, w, h):
    """Mark a rectangular room (border WALL, interior ROOM) on a Grid."""
    g.prog.room(x0, y0, w, h)
    for i in range(w):
        g.set(x0 + i, y0, WALL)
        g.set(x0 + i, y0 + h - 1, WALL)
    for j in range(h):
        g.set(x0, y0 + j, WALL)
        g.set(x0 + w - 1, y0 + j, WALL)
    for ix in range(x0 + 1, x0 + w - 1):
        for iy in range(y0 + 1, y0 + h - 1):
            g.set(ix, iy, ROOM)


# ═══════════════════════════════════════════════════════════════════════════════
# 0. the parity theorem
# ═══════════════════════════════════════════════════════════════════════════════
def t_parity_theorem():
    """Every legal pipe between two FIXED border points has the SAME length parity,
    so slack between two routes of the same net is always EVEN.  Verify empirically:
    enumerate many routes of one net in an open arena and check they all agree."""
    src, dst = (2, 6), (18, 6)
    want = R.pipe_len_parity(src, dst)
    lens = {}
    for k in range(0, 5):
        g = open_grid(24, 20)
        box_room(g, 0, 4, 3, 5)
        box_room(g, 18, 4, 3, 5)
        for y in range(0, 6 + k):            # a barrier of growing depth at x=10
            g.set(10, y, PLACED, "x")
        res = R.route_pipe(g, PipeNet("p", src, dst, ()))
        if res:
            lens[k] = len(res[0])
    check("parity theorem: all routes of one net share length parity",
          len(lens) >= 4 and {n % 2 for n in lens.values()} == {want},
          f"lengths {lens}, predicted parity {want}")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. slack 0
# ═══════════════════════════════════════════════════════════════════════════════
def t_slack0():
    g = open_grid(24, 14)
    box_room(g, 0, 4, 3, 5)
    box_room(g, 18, 4, 3, 5)
    net = PipeNet("p", (2, 6), (18, 6), ())
    base = R.route_pipe(g, net)
    n = len(base[0])
    res = R.route_pipe_len(g, net, n)
    ok = bool(res) and len(res[0]) == n
    if ok:
        validate_both(res[0], res[1], net.src, net.dst)
    check("slack 0: exact-length route == shortest route", ok, repr(res))
    return n


# ═══════════════════════════════════════════════════════════════════════════════
# 2. small even slack
# ═══════════════════════════════════════════════════════════════════════════════
def t_small_slack(base_n):
    for extra in (2, 4, 6, 8):
        g = open_grid(24, 14)
        box_room(g, 0, 4, 3, 5)
        box_room(g, 18, 4, 3, 5)
        net = PipeNet("p", (2, 6), (18, 6), ())
        want = base_n + extra
        res = R.route_pipe_len(g, net, want)
        ok = bool(res) and len(res[0]) == want
        if ok:
            validate_both(res[0], res[1], net.src, net.dst)
        check(f"small slack +{extra}: exact length {want}", ok,
              f"{res if not res else len(res[0])}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. large slack (deep comb)
# ═══════════════════════════════════════════════════════════════════════════════
def t_large_slack(base_n):
    for want in (base_n + 20, base_n + 60, base_n + 120):
        g = open_grid(24, 30)
        box_room(g, 0, 4, 3, 5)
        box_room(g, 18, 4, 3, 5)
        net = PipeNet("p", (2, 6), (18, 6), ())
        res = R.route_pipe_len(g, net, want)
        ok = bool(res) and len(res[0]) == want
        if ok:
            validate_both(res[0], res[1], net.src, net.dst)
        check(f"large slack: exact length {want} (shortest {base_n})", ok,
              f"{res if not res else len(res[0])}")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ODD slack -> must be reported explicitly, never silently mis-sized
# ═══════════════════════════════════════════════════════════════════════════════
def t_odd_slack(base_n):
    g = open_grid(24, 14)
    box_room(g, 0, 4, 3, 5)
    box_room(g, 18, 4, 3, 5)
    net = PipeNet("p", (2, 6), (18, 6), ())
    res = R.route_pipe_len(g, net, base_n + 1)
    check("odd slack: reported as failure (not silently wrong length)",
          (not res) and isinstance(res, R.FoldFailure) and res.reason == "odd-parity",
          repr(res))
    # and the remedy: shifting ONE endpoint by one cell flips the parity
    net2 = PipeNet("p", (2, 6), (18, 7), ())
    b2 = R.route_pipe(g, net2)
    res2 = R.route_pipe_len(g, net2, base_n + 1) if b2 else None
    check("odd slack remedy: endpoint shifted by 1 makes the odd length reachable",
          bool(res2) and len(res2[0]) == base_n + 1, repr(res2))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. obstacles: the fold must FIND the free cells (only one side is open)
# ═══════════════════════════════════════════════════════════════════════════════
def t_obstacles(base_n):
    g = open_grid(24, 20)
    box_room(g, 0, 4, 3, 5)
    box_room(g, 18, 4, 3, 5)
    # seal everything ABOVE the pipe row: folds must go SOUTH
    for x in range(3, 18):
        for y in range(0, 6):
            g.set(x, y, PLACED, "x")
    net = PipeNet("p", (2, 6), (18, 6), ())
    want = base_n + 30
    res = R.route_pipe_len(g, net, want)
    ok = bool(res) and len(res[0]) == want
    if ok:
        validate_both(res[0], res[1], net.src, net.dst)
        ok = all(g.t(*c) == FREE for c in res[0])       # never claimed a busy cell
        ok = ok and all(c[1] >= 6 for c in res[0])      # all folds went SOUTH
    check(f"obstacles: comb found the only free side, exact length {want}", ok,
          f"{res if not res else len(res[0])}")

    # tighter: a 3-cell-deep pocket, everything else sealed
    g2 = open_grid(24, 20)
    box_room(g2, 0, 4, 3, 5)
    box_room(g2, 18, 4, 3, 5)
    for x in range(3, 18):
        for y in list(range(0, 6)) + list(range(10, 20)):
            g2.set(x, y, PLACED, "x")
    net2 = PipeNet("p", (2, 6), (18, 6), ())
    # free pocket for folds: x in 3..17, y in 7..9  =>  15*3 = 45 cells
    res2 = R.route_pipe_len(g2, net2, base_n + 40)
    ok2 = bool(res2) and len(res2[0]) == base_n + 40
    if ok2:
        validate_both(res2[0], res2[1], net2.src, net2.dst)
    check("obstacles: 45-cell pocket absorbs +40 slack", ok2,
          f"{res2 if not res2 else len(res2[0])}")

    # and asking for MORE than the pocket holds must FAIL cleanly
    g3 = open_grid(24, 20)
    box_room(g3, 0, 4, 3, 5)
    box_room(g3, 18, 4, 3, 5)
    for x in range(3, 18):
        for y in list(range(0, 6)) + list(range(10, 20)):
            g3.set(x, y, PLACED, "x")
    res3 = R.route_pipe_len(g3, PipeNet("p", (2, 6), (18, 6), ()), base_n + 200)
    check("impossible slack: clean failure, no partial pipe",
          (not res3) and isinstance(res3, R.FoldFailure)
          and res3.reason == "insufficient-free-area", repr(res3))


# ═══════════════════════════════════════════════════════════════════════════════
# 6. shortening is REFUSED (length is capacity + latency)
# ═══════════════════════════════════════════════════════════════════════════════
def t_no_shorten(base_n):
    g = open_grid(24, 14)
    box_room(g, 0, 4, 3, 5)
    box_room(g, 18, 4, 3, 5)
    net = PipeNet("p", (2, 6), (18, 6), ())
    res = R.route_pipe_len(g, net, base_n - 2)
    check("shortening refused: required < shortest route",
          (not res) and isinstance(res, R.FoldFailure) and res.reason == "too-short",
          repr(res))
    # min_len mode: a route that is ALREADY long enough is accepted as-is
    res2 = R.route_pipe_len(g, net, base_n - 2, mode="min")
    check("mode='min': already-long-enough route accepted unchanged",
          bool(res2) and len(res2[0]) == base_n, repr(res2))


# ═══════════════════════════════════════════════════════════════════════════════
# 7. capacity: how much slack fits per unit of free area
# ═══════════════════════════════════════════════════════════════════════════════
def t_capacity():
    """A comb TILES the rectangle it folds into: 2 path edges x depth k adds 2k cells
    using 2k cells of area, so the ceiling is 1.0 slack per free cell.  Measure the
    fraction actually achieved in a clean rectangular pocket."""
    rows = []
    for depth in (1, 2, 3, 5, 8):
        g = open_grid(40, 40)
        box_room(g, 0, 4, 3, 5)
        box_room(g, 34, 4, 3, 5)
        for x in range(3, 34):
            for y in list(range(0, 6)) + list(range(7 + depth, 40)):
                g.set(x, y, PLACED, "x")
        net = PipeNet("p", (2, 6), (34, 6), ())
        base = R.route_pipe(g, net)
        n = len(base[0])
        area = 31 * depth                    # free cells strictly below the pipe row
        best = 0
        # slack is ALWAYS even (parity theorem), so scan even values only
        for slack in range(2 * ((area + 2) // 2), -1, -2):
            res = R.route_pipe_len(g, net, n + slack)
            if res:
                best = slack
                validate_both(res[0], res[1], net.src, net.dst)
                break
        rows.append((depth, area, best, best / area if area else 0))
    print("\n    depth  free-area  max-slack-absorbed  slack/cell")
    for d, a, b, f in rows:
        print(f"    {d:5d}  {a:9d}  {b:18d}  {f:10.2f}")
    check("capacity: >=0.9 slack absorbed per free cell in a clean pocket",
          all(f >= 0.9 for _, _, _, f in rows), str(rows))
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# 8. false pipe-start hazard: a fold arrow whose BACK neighbour is a room border
#    would be mis-parsed as a second pipe start by the oracle.
# ═══════════════════════════════════════════════════════════════════════════════
def t_false_start():
    g = open_grid(24, 14)
    box_room(g, 0, 4, 3, 5)
    box_room(g, 18, 4, 3, 5)
    # a third room sitting right under the pipe lane, so a naive comb would put a
    # bend arrow directly against its top wall
    box_room(g, 6, 8, 8, 4)
    net = PipeNet("p", (2, 6), (18, 6), ())
    base = R.route_pipe(g, net)
    n = len(base[0])
    res = R.route_pipe_len(g, net, n + 10)
    ok = bool(res) and len(res[0]) == n + 10
    if ok:
        validate_both(res[0], res[1], net.src, net.dst)
        bad = R.false_start_cells(g, res[0], res[1])
        ok = not bad
        if bad:
            print("      false starts:", bad)
    check("no false pipe starts: no bend arrow points out of a room border", ok,
          repr(res))


# ═══════════════════════════════════════════════════════════════════════════════
# 9. END TO END on a real grid: re-route ring-v2's 4 pipes at EXACT length
# ═══════════════════════════════════════════════════════════════════════════════
def t_end_to_end():
    import json
    import littleman as lm
    Rt = R.build_ring_v2_with_router()
    ref_lens = None
    res = Rt.solve(budget=60)
    if res is not True:
        check("end-to-end: ring-v2 baseline solve", False, repr(res))
        return
    ref_lens = {k: len(v[0]) for k, v in Rt._proutes.items()}

    # now re-solve with EXACT length constraints equal to the baseline lengths
    Rt2 = R.build_ring_v2_with_router()
    for i, net in enumerate(Rt2.pipe_nets):
        Rt2.pipe_nets[i] = net._replace(exact_len=ref_lens[net.name])
    res2 = Rt2.solve(budget=60)
    ok = res2 is True and {k: len(v[0]) for k, v in Rt2._proutes.items()} == ref_lens
    check("end-to-end: ring-v2 re-routed at EXACT baseline pipe lengths", ok,
          repr(res2))
    if ok:
        got, want = Rt2.render(), open(os.path.join(
            lm.REPO, "solutions", "reverse-a-list", "ring-v2.man")).read().rstrip("\n")
        check("end-to-end: ring-v2 still byte-identical", got == want, "render differs")
        g = Rt2.grade("reverse-a-list")
        check("end-to-end: ring-v2 still 8/8 @ 956100",
              g.get("passed") == 8 and g.get("score") == 956100, json.dumps(g))

    # and the interesting case: force one pipe LONGER than its shortest route and
    # check the whole program still loads + grades in the REAL ENGINE.
    Rt3 = R.build_ring_v2_with_router()
    for i, net in enumerate(Rt3.pipe_nets):
        if net.name == "RETURN":
            Rt3.pipe_nets[i] = net._replace(exact_len=ref_lens["RETURN"] + 2)
    res3 = Rt3.solve(budget=60)
    ok3 = res3 is True and len(Rt3._proutes["RETURN"][0]) == ref_lens["RETURN"] + 2
    check("end-to-end: RETURN padded by +2 routes and validates", ok3, repr(res3))
    if ok3:
        p = os.path.join(HERE, "ring_v2_return_plus2.man")
        Rt3.prog.save(p)
        g3 = Rt3.grade("reverse-a-list")
        check("end-to-end: padded ring-v2 still loads and passes 8/8 in the ORACLE",
              g3.get("passed") == 8, json.dumps(
                  {k: g3.get(k) for k in ("passed", "total", "avgTicks", "score")}))
        print("      padded ring-v2:", Rt3.footprint(),
              {k: len(v[0]) for k, v in Rt3._proutes.items()},
              "score", g3.get("score"), "(baseline 956100)")

    # STRUCTURAL LIMIT: ring-v2's FEED pipe is 2 cells wedged between two walls — its
    # ONLY edge is edge 0, which can never be folded (it would break the source
    # attachment), and no other cell is adjacent to the destination border.  This must
    # be a clean, explained failure, not a crash or a wrong-length pipe.
    Rt4 = R.build_ring_v2_with_router()
    for i, net in enumerate(Rt4.pipe_nets):
        if net.name == "FEED":
            Rt4.pipe_nets[i] = net._replace(exact_len=ref_lens["FEED"] + 4)
    res4 = Rt4.solve(budget=20)
    check("structural limit: a 2-cell wall-wedged pipe reports a clean failure",
          isinstance(res4, R.UnroutableNet) and res4.which == "FEED"
          and "insufficient-free-area" in res4.why, repr(res4))


if __name__ == "__main__":
    t_parity_theorem()
    n = t_slack0()
    t_small_slack(n)
    t_large_slack(n)
    t_odd_slack(n)
    t_obstacles(n)
    t_no_shorten(n)
    t_capacity()
    t_false_start()
    t_end_to_end()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        sys.exit(1)
    print("ALL FOLDED-ROUTING TESTS PASSED")
