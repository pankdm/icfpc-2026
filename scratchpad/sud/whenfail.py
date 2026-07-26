#!/usr/bin/env python3
"""Is the timer's extra 6-tick requirement a STARTUP transient or steady state?
Same box/lane2 duplicate, pushed progressively later by prefixing valid cells
that touch neither the row, the column nor the box of the colliding pair."""
import subprocess, sys, json
SOL = "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/solutions/sudoku-validity"
man = sys.argv[1]

# the colliding pair: box idx 7 (r in 6..8, c in 3..5), value 5
PAIR = [(6, 3, 5), (7, 4, 5)]
# filler cells: rows 0..5 / cols 0..2, value 5 is never reused there
FILL = [(r, c, 5) for r, c in zip(range(6), range(6))][:0]

def rounds(cells):
    rows, cols, box = set(), set(), set()
    out = []
    for (r, c, v) in cells:
        b = 3 * (r // 3) + (c // 3)
        bad = (r, v) in rows or (c, v) in cols or (b, v) in box
        out.append({"in": [str(r), str(c), str(v)], "out": ["0" if bad else "1"]})
        if bad: break
        rows.add((r, v)); cols.add((c, v)); box.add((b, v))
    return out

for n in (0, 1, 2, 3, 5, 8, 12):
    # n filler cells in rows 0..2 / cols 6..8 (box idx 2), distinct values 1..9
    fill = [(i // 3, 6 + i % 3, 1 + i) for i in range(n)]
    cells = fill + PAIR
    rs = rounds(cells)
    assert rs[-1]["out"] == ["0"], (n, rs[-1])
    o = subprocess.run(["node", "sim/case.js", man, json.dumps(rs)],
                       cwd="/Users/visenbaev/icfpc26", capture_output=True, text=True)
    j = json.loads(o.stdout.strip().splitlines()[-1])
    print(f"dup at round {len(rs):2d}: {j.get('status'):5s} out={j.get('output')}")
