#!/usr/bin/env python3
"""Correctness gate for a sudoku-validity build, self-contained and fast.

  A. 243 exhaustive: every (idx, v) x {row, col, box} as an isolated duplicate.
  B. every (idx, v) as a VALID pair (same value, different row/col/box) so a
     false positive is caught as well as a false negative.
  C. lane-2 duplicates after prefixes of many lengths (latest possible detect).
  D. full 81-round valid scans, shuffled scans, and degenerate shapes.

usage: w2_gate.py <file.man> [jobs]
"""
import json, os, random, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

LM = "/Users/visenbaev/icfpc26/interp/target/release/lm"


def solved_grid(rng):
    base = [[(3 * (r % 3) + r // 3 + c) % 9 + 1 for c in range(9)] for r in range(9)]
    rows = list(range(9))
    for b in range(3):
        blk = rows[3 * b:3 * b + 3]
        rng.shuffle(blk)
        rows[3 * b:3 * b + 3] = blk
    cols = list(range(9))
    for b in range(3):
        blk = cols[3 * b:3 * b + 3]
        rng.shuffle(blk)
        cols[3 * b:3 * b + 3] = blk
    perm = list(range(1, 10))
    rng.shuffle(perm)
    return [[perm[base[r][c] - 1] for c in cols] for r in rows]


def expected(cells):
    """Reference model: emit 1 while valid, 0 on the first collision, then stop."""
    rows = [set() for _ in range(9)]
    colz = [set() for _ in range(9)]
    boxz = [set() for _ in range(9)]
    out = []
    for (r, c, v) in cells:
        b = 3 * (r // 3) + c // 3
        if v in rows[r] or v in colz[c] or v in boxz[b]:
            out.append(((r, c, v), "0"))
            break
        rows[r].add(v); colz[c].add(v); boxz[b].add(v)
        out.append(((r, c, v), "1"))
    return out


def run(man, cells):
    rounds = expected(cells)
    inp = " / ".join("%d %d %d" % rc for rc, _ in rounds)
    exp = " / ".join(o for _, o in rounds)
    p = subprocess.run([LM, "--grade", man, "--input=" + inp, "--expected=" + exp,
                        "--cap=400000"], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"status": "engine-error", "reason": (p.stderr or p.stdout)[:160]}


def suites(rng):
    S = {}
    ex, ok = [], []
    for v in range(1, 10):
        for idx in range(9):
            b = idx + 9 * (v - 1)
            ex.append(("row-%d-%d/b%d" % (idx, v, b), [(idx, 0, v), (idx, 4, v)]))
            ex.append(("col-%d-%d/b%d" % (idx, v, b), [(0, idx, v), (4, idx, v)]))
            r0, c0 = 3 * (idx // 3), 3 * (idx % 3)
            ex.append(("box-%d-%d/b%d" % (idx, v, b),
                       [(r0, c0, v), (r0 + 1, c0 + 1, v)]))
            # same value, different row AND column AND box -> must stay valid
            r1, c1 = idx, (idx * 3 + 1) % 9
            r2, c2 = (idx + 4) % 9, (c1 + 4) % 9
            if r1 != r2 and c1 != c2 and (r1 // 3, c1 // 3) != (r2 // 3, c2 // 3):
                ok.append(("ok-%d-%d/b%d" % (idx, v, b), [(r1, c1, v), (r2, c2, v)]))
    S["dup-exhaustive"] = ex
    S["valid-pairs"] = ok

    g = solved_grid(rng)
    scan = [(r, c, g[r][c]) for r in range(9) for c in range(9)]
    late = []
    for k in range(2, 81, 3):
        pre = scan[:k]
        seen = {(r, v) for (r, c, v) in pre}
        done = {(r, c) for (r, c, v) in pre}
        for (r, c) in [(r, c) for r in range(9) for c in range(9)]:
            if (r, c) in done:
                continue
            got = [v for v in (9, 8, 7) if (r, v) in seen and r + 9 * (v - 1) >= 54]
            if got:
                late.append(("lane2@%d" % k, pre + [(r, c, got[0])]))
                break
    S["lane2-late"] = late

    misc = [("single", [(4, 4, 7)]),
            ("two-far", [(0, 0, 1), (8, 8, 1)]),
            ("immediate-dup", [(0, 0, 5), (0, 8, 5)]),
            ("extremes", [(0, 0, 1), (8, 8, 9), (0, 8, 9), (8, 0, 1)]),
            ("b54-both-lanes", [(0, 0, 7), (0, 4, 7)]),
            ("b53-lane1", [(8, 0, 6), (8, 4, 6)]),
            ("b55-lane2", [(1, 0, 7), (1, 4, 7)])]
    for i in range(14):
        gg = solved_grid(rng)
        cs = [(r, c, gg[r][c]) for r in range(9) for c in range(9)]
        if i % 2:
            rng.shuffle(cs)
        misc.append(("full%d" % i, cs))
    for i in range(10):
        gg = solved_grid(rng)
        cs = [(r, c, gg[r][c]) for r in range(9) for c in range(9)]
        rng.shuffle(cs)
        for k in range(rng.randrange(1, 81), 81):
            r, c, v = cs[k]
            cand = [x for x in range(1, 10)
                    if x != v and any(rc[0] == r and rc[2] == x for rc in cs[:k])]
            if cand:
                cs[k] = (r, c, cand[0])
                misc.append(("dupat%d" % k, cs[:k + 1]))
                break
    S["misc"] = misc
    return S


def main():
    man = os.path.abspath(sys.argv[1])
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    rng = random.Random(20260727)
    bad = 0
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for name, suite in suites(rng).items():
            res = list(ex.map(lambda t: run(man, t[1]), suite))
            fails = [(n, r) for (n, _), r in zip(suite, res) if r.get("status") != "pass"]
            bad += len(fails)
            print("%-16s %3d/%3d pass" % (name, len(suite) - len(fails), len(suite)),
                  flush=True)
            for n, r in fails[:6]:
                print("   FAIL %s %s" % (n, json.dumps(r)[:160]), flush=True)
    print("TOTAL FAILURES:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
