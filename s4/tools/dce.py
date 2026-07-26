#!/usr/bin/env python3
"""dce.py — dead code elimination, then convert the freed space into box.

A cell no man can reach is dead. Blanking it alone is usually worth NOTHING here, because
ticks are cells WALKED, not instructions executed, and a hole in the middle of a grid does
not shrink `max(w,h)`. Measured across every champion: 3-83 dead cells each, and **zero** at
the bounding-box extremes. So DCE on its own is a no-op for score.

It pays only in composition: blanking dead cells turns rows and columns into candidates that
`tools/polish.py` (delete a blank/straight line) and `tools/fold.py` (merge adjacent lines
when no glyph lands in the other's walk path) could not previously touch. This tool therefore
does both halves — eliminate, then re-run the geometry passes on the result — and reports the
score at each stage so the contribution of each is visible rather than assumed.

Reachability comes from `tools/lift.py`, whose walk is cross-checked against the oracle's real
execution (`--verify`), so "unreachable" means the machine provably never executes it, not
that a heuristic thinks so. Branch cells fan out to all three headings, so the reachable set
is an OVER-approximation: anything it calls dead really is dead.

  python3 tools/dce.py <slug> <file.man> [--fold] [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_rows(path):
    text = open(path, encoding="utf-8").read().replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max(len(r) for r in rows) if rows else 0
    return [r.ljust(w) for r in rows]


def lift(path):
    r = subprocess.run(["python3", os.path.join(REPO, "tools", "lift.py"), path, "--json"],
                       capture_output=True, text=True, cwd=REPO)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.exit(f"lift failed: {(r.stderr or r.stdout)[:200]}")


def grade(slug, path, cases=None):
    cmd = ["node", os.path.join(REPO, "tools", "grade_json.js"), slug, path, "--failfast"]
    if cases:
        cmd += ["--cases", cases]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=1800)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stderr or "grade failed")[:160]}


def box_of(rows):
    ys = [i for i, r in enumerate(rows) if r.strip()]
    if not ys:
        return 0, 0, 0
    w = max(len(r) for r in rows)
    xs = [x for x in range(w) if any(len(r) > x and r[x] != " " for r in rows)]
    return xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1, max(xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1) ** 2


def literal_cells(rows):
    """Every cell inside a backtick literal, horizontally and vertically.

    These are load-bearing but frequently NOT walked: a literal is loaded when the man
    crosses its CLOSING backtick, so the digits between can sit on no man's path while still
    defining the value. Blanking one silently changes a constant — it broke gradebook (7/7 ->
    a 5,000,000-tick timeout) and no reachability model would ever have caught it, because
    the cells genuinely are unreachable."""
    out = set()
    h = len(rows)
    w = max(len(r) for r in rows) if rows else 0
    grid = [r.ljust(w) for r in rows]
    for y in range(h):                                   # horizontal
        ticks = [x for x in range(w) if grid[y][x] == "`"]
        for a, b in zip(ticks[0::2], ticks[1::2]):
            span = [grid[y][x] for x in range(a + 1, b)]
            if all(c == " " or c.isdigit() for c in span):
                out.update((x, y) for x in range(a, b + 1))
    for x in range(w):                                   # vertical
        ticks = [y for y in range(h) if grid[y][x] == "`"]
        for a, b in zip(ticks[0::2], ticks[1::2]):
            span = [grid[y][x] for y in range(a + 1, b)]
            if all(c == " " or c.isdigit() for c in span):
                out.update((x, y) for y in range(a, b + 1))
    return out


def dead_cells(rows, ir):
    """Non-blank interior cells no man can reach, excluding literal content."""
    reach = set()
    for m in ir["men"]:
        for k in m.get("reach", []):                 # the full walk, not just block cells
            reach.add(tuple(int(t) for t in k.split(",")))
        for b in m["blocks"]:
            for p, _ in b:
                reach.add(tuple(p))
        for k in m["op_cells"]:
            reach.add(tuple(int(t) for t in k.split(",")))
    interior = set()
    for r in ir["rooms"]:
        (x0, y0), (x1, y1) = r["min"], r["max"]
        for y in range(y0 + 1, y1):
            for x in range(x0 + 1, x1):
                interior.add((x, y))
    # a man START cell is reachable by definition even if the walk record misses it
    for m in ir["men"]:
        reach.add(tuple(m["start"]))
    # An I/O room's `I`/`O` marker sits INSIDE a room interior and no man can ever stand
    # there, so it is formally unreachable — and blanking it removes the program's input or
    # output entirely (gradebook went 7/7 -> a 5,000,000-tick timeout). Unreachable is not
    # the same as unused; only cells whose ONLY role is to be executed are dead.
    protected = {(x, y) for y in range(len(rows)) for x in range(len(rows[y]))
                 if rows[y][x] in "IO"}
    for r in ir["rooms"]:
        (x0, y0), (x1, y1) = r["min"], r["max"]
        if any(rows[y][x] in "IO"
               for y in range(y0 + 1, y1) for x in range(x0 + 1, x1) if x < len(rows[y])):
            protected |= {(x, y) for y in range(y0 + 1, y1) for x in range(x0 + 1, x1)}
    lits = literal_cells(rows)
    return [(x, y) for (x, y) in sorted(interior)
            if rows[y][x] != " " and (x, y) not in reach
            and (x, y) not in lits and (x, y) not in protected]


def blank(rows, cells):
    grid = [list(r) for r in rows]
    for x, y in cells:
        grid[y][x] = " "
    return ["".join(r).rstrip() for r in grid]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("man")
    ap.add_argument("--fold", action="store_true",
                    help="after eliminating, run polish/fold to convert freed space into box")
    ap.add_argument("--cases")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = load_rows(args.man)
    ir = lift(args.man)
    dead = dead_cells(rows, ir)
    W, H, box = box_of(rows)
    ys = [y for _, y in dead]
    xs = [x for x, _ in dead]
    at_edge = [c for c in dead if c[0] in (min(xs), max(xs)) or c[1] in (min(ys), max(ys))] if dead else []
    print(f"{os.path.basename(args.man)}: {W}x{H} box {box}, {len(dead)} dead cells "
          f"({len(at_edge)} at the bbox edge — only those can shrink the box directly)")
    if not dead:
        print("  nothing to eliminate")
        return
    if args.dry_run:
        print(f"  would blank: {dead[:12]}{' …' if len(dead) > 12 else ''}")
        return

    base = grade(args.slug, args.man, args.cases)
    if base.get("error") or base["passed"] != base["total"]:
        sys.exit(f"baseline does not pass: {base}")
    print(f"  baseline {base['passed']}/{base['total']} score {base['score']:,.0f}")

    cand = blank(rows, dead)
    out = os.path.splitext(args.man)[0] + "-dce.man"
    open(out, "w").write("\n".join(cand) + "\n")
    g = grade(args.slug, out, args.cases)
    nW, nH, nbox = box_of(cand)
    ok = not g.get("error") and g["passed"] == g["total"]
    print(f"  after DCE: {g.get('passed')}/{g.get('total')} box {box}->{nbox} "
          f"score {g.get('score', 0):,.0f}" if ok else f"  after DCE: FAILED {g}")
    if not ok:
        os.remove(out)
        sys.exit("  dead-cell removal broke the program — the reachability set is wrong, "
                 "which is a lift.py bug worth reporting")

    # The point of DCE here: freed cells may make whole lines deletable/foldable.
    if args.fold:
        for tool, flag in (("polish.py", None), ("fold.py", None)):
            path = os.path.join(REPO, "tools", tool)
            if not os.path.exists(path):
                continue
            r = subprocess.run(["python3", path, args.slug, out] + ([flag] if flag else []),
                               capture_output=True, text=True, cwd=REPO, timeout=3600)
            tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-3:]
            print(f"  {tool}: " + " | ".join(t.strip() for t in tail))
    print(f"\nwrote {os.path.relpath(out, REPO)}")
    print(f"verify: node tools/grade.js {args.slug} {os.path.relpath(out, REPO)}")


if __name__ == "__main__":
    main()
