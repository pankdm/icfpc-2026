#!/usr/bin/env python3
"""Unit tests for tools/evacuate.py — the EVACUATE A LINE move.

Four scenarios, each a hand-built grid small enough to read:

  1. ONE crossing pipe on the line       -> evacuated, box shrinks, engine agrees
  2. SEVERAL crossing pipes on the line  -> evacuated, all lengths exact
  3. a pipe that CANNOT avoid the line   -> clean, named failure (not a crash, not a ship)
  4. evacuation routes but the BINDING moves -> REJECTED

  python3 scratchpad/evac_tests.py
"""
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm          # noqa: E402
import place as P               # noqa: E402
import evacuate as E            # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(("[ok] " if cond else "[FAIL] ") + name + (f"  {detail}" if detail else ""))
    if not cond:
        FAILED.append(name)


def write(prog):
    fh = tempfile.NamedTemporaryFile("w", suffix=".man", delete=False)
    fh.write(prog.render() + "\n")
    fh.close()
    return fh.name


def show(path):
    print("    " + open(path).read().replace("\n", "\n    ").rstrip())


# ══════════════════════════════════════════════════════════════════════════════
# 1. ONE pipe crosses the line.  Two rooms side by side; the pipe between them
#    dives DOWN into empty space and comes back, so the rows it dives through hold
#    nothing but pipe.  Both endpoints are on the SAME side of those rows, so no
#    pipe SPANS them: a shear-free, parity-clean candidate.
# ══════════════════════════════════════════════════════════════════════════════
def build_one():
    p = lm.Program()
    p.room(0, 0, 5, 4)                      # A: (0,0)-(4,3)
    p.text(1, 1, "@s")
    p.room(6, 0, 5, 4)                      # B: (6,0)-(10,3)
    p.text(7, 1, "@r")
    # A bottom wall (2,3) -> dive to y=16 -> east -> climb -> B bottom wall (8,3).
    # 11 wide, 17 tall: HEIGHT is the binding axis, so a deleted row is worth a box.
    p.pipe([(2, 4), (2, 16), (8, 16), (8, 4)], end_direction="N")
    return p


def test_one():
    path = write(build_one())
    print("\n--- 1. one crossing pipe " + "-" * 46)
    show(path)
    plan = P.Plan(path)
    reps = {r.index: r for r in E.scan_lines(plan, "row")}
    cands = [i for i, r in reps.items() if r.verdict == "candidate"]
    check("scan finds pipe-only rows with no spanning pipe",
          cands == list(range(4, 17)), f"rows {cands}")
    res = E.evacuate_line(plan, "row", 10, allow_grow=False)
    check("evacuate_line(row 10) succeeds", bool(res), repr(res))
    if not res:
        return
    check("box shrank", res.after[2] < res.before[2],
          f"{res.before[2]} -> {res.after[2]}")
    check("height dropped by exactly 1", res.after[1] == res.before[1] - 1,
          f"{res.before[1]} -> {res.after[1]}")
    lens_before = [p_.length for p_ in plan.pipes]
    lens_after = [len(c) for c, _d in res.paths]
    check("every pipe kept its EXACT length", lens_before == lens_after,
          f"{lens_before} -> {lens_after}")
    err, ends = E.engine_parse_text(res.text)
    check("the engine loads the result", err is None, str(err))
    check("the engine still sees exactly 1 pipe", len(ends) == 1, str(ends))
    print("    result:\n    " + res.text.replace("\n", "\n    ").rstrip())


# ══════════════════════════════════════════════════════════════════════════════
# 2. SEVERAL pipes cross the same line.  Two independent room pairs, each with its
#    own dive, both bottoming out on the same rows.  Every pipe must be re-routed
#    off the line at exact length simultaneously.
# ══════════════════════════════════════════════════════════════════════════════
def build_many():
    p = lm.Program()
    p.room(0, 0, 5, 4)                      # A: (0,0)-(4,3)
    p.text(1, 1, "@s")
    p.room(6, 0, 5, 4)                      # B: (6,0)-(10,3)
    p.text(7, 1, "@r")
    p.pipe([(2, 4), (2, 20), (8, 20), (8, 4)], end_direction="N")     # A -> B, inner U
    p.pipe([(9, 4), (9, 22), (1, 22), (1, 4)], end_direction="N")     # B -> A, outer U
    return p


def test_many():
    path = write(build_many())
    print("\n--- 2. several crossing pipes " + "-" * 41)
    show(path)
    plan = P.Plan(path)
    reps = {r.index: r for r in E.scan_lines(plan, "row")}
    line = 10
    check(f"row {line} carries BOTH pipes", sorted(reps[line].pipes) == [0, 1],
          str(reps[line].pipes))
    check(f"row {line} is a candidate (nothing spans it)",
          reps[line].verdict == "candidate", reps[line].verdict)
    res = E.evacuate_line(plan, "row", line, allow_grow=False)
    check(f"evacuate_line(row {line}) succeeds", bool(res), repr(res))
    if not res:
        return
    lens_before = sorted(p_.length for p_ in plan.pipes)
    lens_after = sorted(len(c) for c, _d in res.paths)
    check("both pipes kept their EXACT lengths", lens_before == lens_after,
          f"{lens_before} -> {lens_after}")
    check("box shrank", res.after[2] < res.before[2],
          f"{res.before[2]} -> {res.after[2]}")
    err, ends = E.engine_parse_text(res.text)
    check("the engine loads the result and still sees 2 pipes",
          err is None and len(ends) == 2, f"{err} {ends}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. A pipe that CANNOT avoid the line.  Two ways for that to be true, and the tool
#    must name each rather than crash or ship:
#      (a) the pipe SPANS the line   -> parity of its length flips; unreachable
#      (b) the line is the last row and a pipe ATTACHES through it -> no first/last cell
# ══════════════════════════════════════════════════════════════════════════════
def build_spanning():
    p = lm.Program()
    p.room(0, 0, 6, 4)                      # A on top
    p.text(1, 1, "@s")
    p.room(0, 10, 6, 4)                     # B underneath
    p.text(1, 11, "@r")
    p.pipe([(2, 4), (2, 6), (4, 6), (4, 9)], end_direction="S")
    return p


def test_cannot():
    path = write(build_spanning())
    print("\n--- 3. a pipe that cannot avoid the line " + "-" * 30)
    show(path)
    plan = P.Plan(path)
    reps = {r.index: r for r in E.scan_lines(plan, "row")}
    check("rows between the rooms are 'shearable', never 'candidate'",
          all(reps[i].verdict == "shearable" for i in (4, 5, 6, 7, 8, 9)),
          str({i: reps[i].verdict for i in (4, 5, 6, 7, 8, 9)}))
    res = E.evacuate_line(plan, "row", 6)
    check("shear-free evacuation FAILS", not res, repr(res))
    check("...and names the parity theorem", res.reason.startswith("pipe-spans-line"),
          res.reason[:70])
    check("...and ships nothing", res.text is None)

    # (b) the last row carries a pipe's attachment
    p2 = lm.Program()
    p2.room(0, 0, 6, 4)
    p2.text(1, 1, "@s")
    p2.room(0, 6, 4, 4)
    p2.text(1, 7, "@r")
    # A right wall -> east -> down the far side -> west -> up into B's BOTTOM wall,
    # so the pipe's LAST cell lives on the grid's last row
    p2.pipe([(6, 1), (10, 1), (10, 10), (2, 10)], end_direction="N")
    path2 = write(p2)
    print()
    show(path2)
    plan2 = P.Plan(path2)
    res2 = E.evacuate_line(plan2, "row", 10, shear=0)
    check("deleting the row a pipe ATTACHES through fails cleanly", not res2, repr(res2))
    check("...named endpoint-boxed-in or pipe-spans-line",
          res2.reason.split()[0] in ("endpoint-boxed-in", "pipe-spans-line"),
          res2.reason[:70])


# ══════════════════════════════════════════════════════════════════════════════
# 4. Evacuation ROUTES but the binding MOVES -> must be REJECTED.
#
#    A pipe attached at a room CORNER is the one case where `cells[0]` has two legal
#    positions (out to the side, or straight down past the corner), so a re-route can
#    silently move the cell that `s`/`r` measure their Manhattan distance to.  Two
#    outgoing pipes plus two `s` ops make that visible as a changed binding.
#
#    The test is written so it PASSES either by observing the rejection on a real
#    re-route, or — if the router happens to reproduce the original attach — by
#    checking the guard fires when the binding genuinely differs.  What it must never
#    do is return an EvacResult that is ok while the resolution differs from base.
# ══════════════════════════════════════════════════════════════════════════════
def build_corner():
    p = lm.Program()
    p.room(0, 0, 9, 5)                      # A: two outgoing pipes, two 's' ops
    p.text(1, 1, "@s")
    p.text(7, 1, "s")     # far right: bound to the RIGHT pipe, not the left one
    p.room(0, 10, 5, 4)                     # B
    p.text(1, 11, "@r")
    p.room(12, 10, 5, 4)                    # C
    p.text(13, 11, "@r")
    p.pipe([(0, 5), (0, 8), (2, 8), (2, 9)], end_direction="S")     # A bottom-left -> B
    p.pipe([(8, 5), (8, 8), (14, 8), (14, 9)], end_direction="S")   # A bottom-right -> C
    return p


def test_binding_guard():
    path = write(build_corner())
    print("\n--- 4. binding must not move " + "-" * 42)
    show(path)
    plan = P.Plan(path)
    base = dict(plan.base_resolution)
    room0 = {k: v for k, v in base.items() if k[0] is False and k[1] == 0}
    check("room 0's two 's' ops bind to DIFFERENT pipes",
          len(set(room0.values())) == 2, str(room0))

    # every result this tool ever returns must agree with the base resolution
    bad, okd = [], []
    for line in range(0, 14):
        for sh in (0, -1, 1):
            r = E.evacuate_line(plan, "row", line, shear=sh)
            if r:
                okd.append((line, sh))
                if plan.resolution(r.layout, r.paths) != plan.base_resolution:
                    bad.append((line, sh))
    check("the grid HAS evacuable lines (so the next check is not vacuous)",
          bool(okd), str(okd[:6]))
    check("no accepted evacuation ever changes the binding", not bad, str(bad))

    # ...and those same lines must be REJECTED once the expected binding differs, which
    # is exactly "evacuation routes fine but an s/r silently retargets"
    victim = next(k for k in plan.base_resolution if isinstance(k[1], int))
    plan.base_resolution = dict(plan.base_resolution)
    plan.base_resolution[victim] = "not-this-pipe"
    hits = [E.evacuate_line(plan, "row", line, shear=sh)
            for line in range(0, 14) for sh in (0, -1, 1)]
    check("with the binding perturbed, every previously-good line is REJECTED",
          not any(hits))
    check("...with the binding reason, not a routing one",
          any(h.reason == "nearest-pipe resolution changed" for h in hits),
          sorted({h.reason.split("(")[0][:40] for h in hits})[:3])

    # the ENGINE gate is the other half of the same guarantee: a grid that routes and
    # binds perfectly can still be re-parsed into different pipes (measured on matmul)
    err, ends = E.engine_parse(path)
    check("engine_check accepts a faithful parse of the baseline",
          E.engine_check(open(path).read(), ends)[0] is None)
    check("engine_check rejects, and localises, an invented pipe",
          E.engine_check(open(path).read(), ends[:-1])[0] is not None
          and E.engine_check(open(path).read(), ends[:-1])[1])


if __name__ == "__main__":
    test_one()
    test_many()
    test_cannot()
    test_binding_guard()
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: {FAILED}")
        sys.exit(1)
    print("ALL EVACUATE TESTS PASSED")
