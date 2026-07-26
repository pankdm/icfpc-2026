#!/usr/bin/env python3
"""Bisect the timer-LAP cliff for build_lanes9.

lanes9 re-encodes the bit as idx + 9*(v-1), so which lane a cell uses is NOT what
it was in lanes8: shift1 = 54 - bit, so lane1 covers bit <= 54 and lane2 covers
bit >= 55, i.e. lane2 is (roughly) v >= 7.  The lane2 mask is the LAST thing an
addressing room sends, so lane2 duplicates are what gate the cliff -- and a
lane1-only suite passes at laps where lane2 is silently missed.

usage: cliff9.py <lo-lap> <hi-lap> [step]
"""
import json, subprocess, sys

WT = "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a"
SOL = f"{WT}/solutions/sudoku-validity"


def lane(idx, v):
    return 1 if 54 - (idx + 9 * (v - 1)) >= 0 else 2


def dup_rounds(cells):
    rows, cols, box = set(), set(), set()
    out = []
    for (r, c, v) in cells:
        b = 3 * (r // 3) + (c // 3)
        bad = (r, v) in rows or (c, v) in cols or (b, v) in box
        out.append({"in": [str(r), str(c), str(v)], "out": ["0" if bad else "1"]})
        if bad:
            break
        rows.add((r, v)); cols.add((c, v)); box.add((b, v))
    return out


# round-2 duplicates on each constraint, in each lane
CASES = {
    "row-lane2":  [(8, 0, 9), (8, 8, 9)],      # row idx 8, v 9 -> bit 80, lane2
    "row-lane2b": [(1, 0, 7), (1, 8, 7)],      # bit 55, the very first lane2 bit
    "col-lane2":  [(0, 8, 9), (8, 8, 9)],
    "box-lane2":  [(6, 6, 9), (8, 7, 9)],
    "box-lane2b": [(0, 0, 8), (1, 1, 8)],
    "row-lane1":  [(8, 0, 1), (8, 8, 1)],
    "col-lane1":  [(0, 8, 1), (8, 8, 1)],
    "box-lane1":  [(0, 0, 1), (1, 1, 1)],
    "extremes":   [(0, 0, 1), (8, 8, 9), (0, 8, 9), (8, 0, 1)],
}


def main():
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    for lap in range(lo, hi + 1, step):
        b = subprocess.run([sys.executable, f"{SOL}/build_lanes9.py", "--lap", str(lap),
                            "-o", "probe9.man"], capture_output=True, text=True)
        if b.returncode:
            print(f"LAP={lap:3d} BUILD-FAIL"); continue
        man = f"{SOL}/probe9.man"
        bad = []
        for name, cells in CASES.items():
            o = subprocess.run(["node", "sim/case.js", man, json.dumps(dup_rounds(cells))],
                               cwd=WT, capture_output=True, text=True)
            try:
                st = json.loads(o.stdout.strip().splitlines()[-1]).get("status")
            except Exception:
                st = "ERR"
            if st != "pass":
                bad.append(name)
        g = subprocess.run(["node", "tools/grade.js", "sudoku-validity", man],
                           cwd=WT, capture_output=True, text=True)
        pub = next((l.split("]")[-1].strip() for l in g.stdout.splitlines()
                    if "public" in l), "?")
        sc = next((l.strip() for l in g.stdout.splitlines() if "SCORE" in l), "?")
        print(f"LAP={lap:3d} adv={'OK' if not bad else 'FAIL:' + ','.join(bad)}"
              f"  {pub}  {sc}")
        sys.stdout.flush()


main()
