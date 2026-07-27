#!/usr/bin/env python3
"""Full correctness gate for a sudoku-validity build, on the Rust engine.

  1. 243 exhaustive: every (idx, v) pair for every constraint type, as an isolated
     two-cell duplicate that fires ONLY that constraint.
  2. lane-2 duplicates at many round positions (the lane whose mask an addressing
     room sends LAST, so the latest possible detection).
  3. the fuzz suite from scratchpad/sud/fuzz.py (valid grids, late violations,
     degenerate shapes).

usage: gate.py <file.man> [jobs]
"""
import json, os, random, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

WT = "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg"
LM = os.path.join(WT, "interp/target/release/lm")
sys.path.insert(0, os.path.join(WT, "scratchpad/sud"))
import fuzz


def bit(idx, v):
    return idx + 9 * (v - 1)


def run(man, cells):
    rounds = fuzz.expected(cells)
    inp = " / ".join(" ".join(r["in"]) for r in rounds)
    exp = " / ".join(" ".join(r["out"]) for r in rounds)
    p = subprocess.run([LM, "--grade", man, "--input=" + inp, "--expected=" + exp,
                        "--cap=60000"], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"status": "engine-error", "reason": (p.stderr or p.stdout)[:160]}


def exhaustive():
    """243 isolated duplicates: (type, idx, v) -> two cells that trip ONLY that type."""
    out = []
    for v in range(1, 10):
        for idx in range(9):
            # ROW idx: same row, columns in different box-columns
            out.append(("row-%d-%d/bit%d" % (idx, v, bit(idx, v)),
                        [(idx, 0, v), (idx, 4, v)]))
            # COL idx: same column, rows in different box-rows
            out.append(("col-%d-%d/bit%d" % (idx, v, bit(idx, v)),
                        [(0, idx, v), (4, idx, v)]))
            # BOX idx: same box, different row AND different column
            r0, c0 = 3 * (idx // 3), 3 * (idx % 3)
            out.append(("box-%d-%d/bit%d" % (idx, v, bit(idx, v)),
                        [(r0, c0, v), (r0 + 1, c0 + 1, v)]))
    return out


def lane2_positions(rng, want=21):
    """Valid prefixes of increasing length, each closed by a lane-2 duplicate.

    lane2 fires when bit = idx + 9*(v-1) >= 54, i.e. for v >= 7 at any idx.
    """
    grid = fuzz.solved_grid(rng)
    scan = [(r, c, grid[r][c]) for r in range(9) for c in range(9)]
    cases = []
    for k in range(2, 81, max(1, 79 // want)):
        pre = scan[:k]
        seen = {(r, v) for (r, c, v) in pre}
        done = {(r, c) for (r, c, v) in pre}
        pick = None
        for (r, c) in [(r, c) for r in range(9) for c in range(9)]:
            if (r, c) in done:
                continue
            for v in (9, 8, 7):
                if (r, v) in seen and bit(r, v) >= 54:
                    pick = (r, c, v)
                    break
            if pick:
                break
        if pick:
            cases.append(("lane2@%d/bit%d" % (k, bit(pick[0], pick[2])), pre + [pick]))
        if len(cases) >= want:
            break
    return cases


def main():
    man = os.path.abspath(sys.argv[1])
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    rng = random.Random(20260726)

    suites = {"exhaustive": exhaustive(), "lane2": lane2_positions(rng)}

    # the fuzz suite, rebuilt here so it runs on the fast engine
    fz = []
    g = fuzz.solved_grid(rng)
    fz.append(("valid-scan", fuzz.cells_of(g, rng, shuffle=False)))
    fz.append(("valid-shuffled", fuzz.cells_of(g, rng)))
    g = fuzz.solved_grid(rng)
    cs = fuzz.cells_of(g, rng, shuffle=False)
    r, c, v = cs[-1]
    cs[-1] = (r, c, g[r][0] if g[r][0] != v else g[r][1])
    fz.append(("last-cell-row-dup", cs))
    for kind in ("row", "col", "box"):
        for _ in range(2):
            g = fuzz.solved_grid(rng)
            cs = fuzz.cells_of(g, rng, shuffle=False)
            while True:
                i = rng.randrange(20, 81)
                r, c, v = cs[i]
                if kind == "row":
                    c2 = rng.randrange(9)
                    if c2 // 3 == c // 3 or g[r][c2] == v:
                        continue
                    nv = g[r][c2]
                elif kind == "col":
                    r2 = rng.randrange(9)
                    if r2 // 3 == r // 3 or g[r2][c] == v:
                        continue
                    nv = g[r2][c]
                else:
                    r2 = 3 * (r // 3) + rng.randrange(3)
                    c2 = 3 * (c // 3) + rng.randrange(3)
                    if (r2, c2) == (r, c) or r2 == r or c2 == c:
                        continue
                    nv = g[r2][c2]
                cs[i] = (r, c, nv)
                break
            fz.append(("%s-dup@%d" % (kind, i), cs))
    fz += [("single-cell", [(4, 4, 7)]),
           ("two-cells", [(0, 0, 1), (8, 8, 1)]),
           ("immediate-dup", [(0, 0, 5), (0, 8, 5)]),
           ("extremes", [(0, 0, 1), (8, 8, 9), (0, 8, 9), (8, 0, 1)]),
           ("boundary-b54", [(0, 0, 7), (0, 4, 7)]),      # bit 54: BOTH lanes
           ("boundary-b53", [(8, 0, 6), (8, 4, 6)]),      # bit 53: lane1 only
           ("boundary-b55", [(1, 0, 7), (1, 4, 7)])]      # bit 55: lane2 only
    for i in range(12):
        g = fuzz.solved_grid(rng)
        fz.append(("rand%d" % i, fuzz.cells_of(g, rng)))
    suites["fuzz"] = fz

    bad = 0
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for sname, suite in suites.items():
            res = list(ex.map(lambda t: run(man, t[1]), suite))
            fails = [(n, r) for (n, _), r in zip(suite, res) if r.get("status") != "pass"]
            bad += len(fails)
            print("%-12s %3d/%3d pass" % (sname, len(suite) - len(fails), len(suite)))
            for n, r in fails[:8]:
                print("   FAIL %s  %s" % (n, json.dumps(r)[:200]))
    print("TOTAL FAILURES:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
