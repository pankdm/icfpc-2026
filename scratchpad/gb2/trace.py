#!/usr/bin/env python3
"""Print the (tick, cell, glyph, A, B, BP) walk of man0 in room0 for a chosen workload.

usage: trace.py <man> <kind> <N> <K> [start_tick] [count]
"""
import json, subprocess, sys, os

REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "scratchpad"))
from gb_bench import build, KINDS, LM

man = sys.argv[1]
kind = sys.argv[2] if len(sys.argv) > 2 else "AVG"
N = int(sys.argv[3]) if len(sys.argv) > 3 else 4
K = int(sys.argv[4]) if len(sys.argv) > 4 else 1
t0 = int(sys.argv[5]) if len(sys.argv) > 5 else 0
cnt = int(sys.argv[6]) if len(sys.argv) > 6 else 200

inp, exp = build(N, K, KINDS[kind], 1, 1)
steps = t0 + cnt
p = subprocess.run([LM, man, str(steps), f"--input={inp}", f"--expected={exp}",
                    "--cap=5000000"], capture_output=True, text=True)
rows = open(man).read().split("\n")
prev = None
for i, line in enumerate(p.stdout.splitlines()):
    if i < t0:
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    rs = d.get("runners") or d.get("men") or []
    if not rs:
        continue
    m = rs[0]
    x, y = m["pos"]
    ch = rows[y][x] if y < len(rows) and x < len(rows[y]) else " "
    if os.environ.get("GLYPHS_ONLY") and ch == " ":
        continue
    print(f"t={i:6d} ({x:2d},{y:2d}) {ch} A={m['a']} B={m['b']} BP={m['backpack']} d={m['dir'][0]},{m['dir'][1]}")
