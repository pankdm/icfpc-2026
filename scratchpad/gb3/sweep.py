#!/usr/bin/env python3
"""Sweep every permutation of the four (identical) ring rooms; keep the ones that fit."""
import itertools, json, subprocess, sys, os
REPO = "/Users/visenbaev/icfpc26"
SRC = sys.argv[1] if len(sys.argv) > 1 else f"{REPO}/solutions/gradebook/gradebook-fold64b.man"
RINGS = [(8, 11), (14, 17), (20, 23), (26, 29)]
best = []
for perm in itertools.permutations(range(4)):
    pin = ",".join(f"{RINGS[i][0]}:{RINGS[perm[i]][0]}" for i in range(4))
    pout = ",".join(f"{RINGS[i][1]}:{RINGS[perm[i]][1]}" for i in range(4))
    out = f"{REPO}/scratchpad/gb3/p_{''.join(map(str, perm))}.man"
    r = subprocess.run([sys.executable, f"{REPO}/scratchpad/gb3/slide.py", SRC, out,
                        "--in", pin, "--out", pout], capture_output=True, text=True)
    line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    if "0 refusals" not in line:
        continue
    gr = subprocess.run([sys.executable, f"{REPO}/tools/grade_fast.py", "gradebook", out],
                        capture_output=True, text=True)
    try:
        d = json.loads(gr.stdout.strip().splitlines()[-1])
    except Exception:
        continue
    if d["passed"] != d["total"]:
        print(f"  {perm} fits but FAILS {d['passed']}/{d['total']}")
        continue
    best.append((d["score"], d["avgTicks"], perm, out))
    print(f"  {perm} OK  avgTicks={d['avgTicks']:.1f} score={d['score']:.0f}")
best.sort()
print("\nbest:", best[0] if best else "none")
