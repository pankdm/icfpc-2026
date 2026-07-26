#!/usr/bin/env python3
"""Bisect the timer-LAP cliff for a lanes builder, using the public suite plus the
adversarial lane2/box duplicates the public suite misses.

usage: cliff.py <builder.py> <lo> <hi>
"""
import subprocess, sys, json, os

WT = "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a"
SOL = f"{WT}/solutions/sudoku-validity"

CASES = {
    "lane2-box-dup@2":  [(6, 3, 5), (7, 4, 5)],
    "lane2-box-dup@2b": [(6, 6, 9), (8, 7, 9)],
    "lane2-row-dup@2":  [(7, 0, 1), (7, 8, 1)],
    "lane2-col-dup@2":  [(0, 8, 9), (8, 8, 9)],
    "lane1-box-dup@2":  [(0, 0, 1), (1, 1, 1)],
    "immediate-dup":    [(0, 0, 5), (0, 8, 5)],
}

def rounds(cells):
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

def probe(builder, tot, tag="probe"):
    man = f"{SOL}/{tag}.man"
    o = subprocess.run([sys.executable, f"{SOL}/{builder}", str(tot), f"{tag}.man"],
                       capture_output=True, text=True)
    if o.returncode:
        return man, None, o.stderr.strip().splitlines()[-1:] or ["build fail"]
    lap = int(o.stdout.split("LAP")[1].split()[0])
    return man, lap, None

def main():
    builder = sys.argv[1]
    lo, hi = int(sys.argv[2]), int(sys.argv[3])
    for tot in range(lo, hi + 1):
        man, lap, err = probe(builder, tot)
        if err:
            print(f"tot={tot:3d} BUILD-FAIL {err}")
            continue
        bad = []
        for name, cells in CASES.items():
            o = subprocess.run(["node", "sim/case.js", man, json.dumps(rounds(cells))],
                               cwd=WT, capture_output=True, text=True)
            try:
                j = json.loads(o.stdout.strip().splitlines()[-1])
            except Exception:
                j = {"status": "ERR"}
            if j.get("status") != "pass":
                bad.append(name)
        g = subprocess.run(["node", "tools/grade.js", "sudoku-validity", man],
                           cwd=WT, capture_output=True, text=True)
        pub = [l for l in g.stdout.splitlines() if "public" in l]
        sc = [l for l in g.stdout.splitlines() if "SCORE" in l]
        print(f"tot={tot:3d} LAP={lap:4d} adv={'OK' if not bad else 'FAIL:'+','.join(bad)}"
              f"  {pub[0].split(']')[-1].strip() if pub else '?'}  {sc[0].strip() if sc else '?'}")
        sys.stdout.flush()

main()
