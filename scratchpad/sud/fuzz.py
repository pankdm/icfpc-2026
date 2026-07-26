#!/usr/bin/env python3
"""Reference sudoku auditor + case generator/runner for the PoC."""
import json, random, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"

def expected(cells):
    """cells: list of (r,c,v). Returns rounds [{'in':[...], 'out':[...]}] truncated
    at the first invalid cell, exactly like the official cases."""
    rows, cols, box = set(), set(), set()
    rounds = []
    for (r, c, v) in cells:
        b = 3 * (r // 3) + (c // 3)
        bad = (r, v) in rows or (c, v) in cols or (b, v) in box
        rounds.append({"in": [str(r), str(c), str(v)], "out": ["0" if bad else "1"]})
        if bad:
            break
        rows.add((r, v)); cols.add((c, v)); box.add((b, v))
    return rounds

def solved_grid(rng):
    base = [[(3 * (r % 3) + r // 3 + c) % 9 + 1 for c in range(9)] for r in range(9)]
    def perm():                      # band-preserving: shuffle bands, then within
        bands = [0, 1, 2]; rng.shuffle(bands)
        out = []
        for b in bands:
            inner = [3 * b, 3 * b + 1, 3 * b + 2]; rng.shuffle(inner)
            out += inner
        return out
    rp, cp = perm(), perm()
    vp = [0] + rng.sample(range(1, 10), 9)
    g = [[vp[base[rp[r]][cp[c]]] for c in range(9)] for r in range(9)]
    assert all(len({g[r][c] for c in range(9)}) == 9 for r in range(9))
    assert all(len({g[r][c] for r in range(9)}) == 9 for c in range(9))
    assert all(len({g[3*(i//3)+a][3*(i%3)+b] for a in range(3) for b in range(3)}) == 9
               for i in range(9))
    return g

def cells_of(grid, rng, shuffle=True):
    cs = [(r, c, grid[r][c]) for r in range(9) for c in range(9)]
    if shuffle:
        rng.shuffle(cs)
    return cs

def run(manfile, rounds):
    out = subprocess.run(["node", "sim/case.js", manfile, json.dumps(rounds)],
                         cwd=REPO, capture_output=True, text=True)
    try:
        return json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": (out.stdout + out.stderr)[:400]}

def main():
    manfile = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    rng = random.Random(20260726)
    suite = []

    # 1. a full valid grid, in scan order and shuffled
    g = solved_grid(rng)
    suite.append(("valid-scan", cells_of(g, rng, shuffle=False)))
    suite.append(("valid-shuffled", cells_of(g, rng)))

    # 2. violation on the very last cell (the adversarial ordering case)
    g = solved_grid(rng)
    cs = cells_of(g, rng, shuffle=False)
    r, c, v = cs[-1]
    cs[-1] = (r, c, g[r][0] if g[r][0] != v else g[r][1])   # duplicate in that row
    suite.append(("last-cell-row-dup", cs))

    # 3. one violation of each kind, injected at a random late position
    for kind in ("row", "col", "box"):
        for trial in range(2):
            g = solved_grid(rng)
            cs = cells_of(g, rng, shuffle=False)
            while True:
                i = rng.randrange(20, 81)
                r, c, v = cs[i]
                if kind == "row":
                    c2 = rng.randrange(9)
                    if c2 // 3 == c // 3 or g[r][c2] == v: continue
                    nv = g[r][c2]
                elif kind == "col":
                    r2 = rng.randrange(9)
                    if r2 // 3 == r // 3 or g[r2][c] == v: continue
                    nv = g[r2][c]
                else:
                    r2, c2 = 3 * (r // 3) + rng.randrange(3), 3 * (c // 3) + rng.randrange(3)
                    if (r2, c2) == (r, c) or r2 == r or c2 == c: continue
                    nv = g[r2][c2]
                cs[i] = (r, c, nv)
                break
            suite.append((f"{kind}-dup@{i}", cs))

    # 4. tiny/degenerate
    suite.append(("single-cell", [(4, 4, 7)]))
    suite.append(("two-cells", [(0, 0, 1), (8, 8, 1)]))
    suite.append(("immediate-dup", [(0, 0, 5), (0, 8, 5)]))
    suite.append(("extremes", [(0, 0, 1), (8, 8, 9), (0, 8, 9), (8, 0, 1)]))

    # 5. random extra valid grids
    for i in range(n):
        g = solved_grid(rng)
        suite.append((f"rand{i}", cells_of(g, rng)))

    bad = 0
    for name, cells in suite:
        rounds = expected(cells)
        res = run(manfile, rounds)
        ok = res.get("status") == "pass"
        if not ok:
            bad += 1
            print(f"FAIL {name}: rounds={len(rounds)} {json.dumps(res)[:300]}")
        else:
            print(f"ok   {name}: rounds={len(rounds)} ticks={res['ticks']}")
    print(f"\n{len(suite)-bad}/{len(suite)} pass")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
