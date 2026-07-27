#!/usr/bin/env python3
"""Stress a sort-numbers .man on hand-built edge cases (rust engine)."""
import json, random, subprocess, sys
ROOT = "/Users/visenbaev/icfpc26"
LM = ROOT + "/interp/target/release/lm"
man = sys.argv[1]

random.seed(7)
cases = {
    "n1 x3": [[5], [-10000], [10000]],
    "n2": [[2, 1], [1, 2], [7, 7]],
    "equal16": [[3] * 16, [-4] * 16],
    "desc16": [list(range(16, 0, -1))],
    "asc16": [list(range(1, 17))],
    "extremes": [[10000, -10000, 0, 10000, -10000]],
    "dups16": [[1, 1, 2, 2, 3, 3, 4, 4, 0, 0, -1, -1, -2, -2, 9, 9]],
    "six rounds": [[random.randint(-10000, 10000) for _ in range(random.randint(1, 16))]
                   for _ in range(6)],
    "all n": [[random.randint(-10000, 10000) for _ in range(k)] for k in range(1, 7)],
}
bad = 0
for name, rounds in cases.items():
    inp = " / ".join(" ".join([str(len(r))] + [str(v) for v in r]) for r in rounds)
    exp = " / ".join(" ".join(str(v) for v in sorted(r)) for r in rounds)
    p = subprocess.run([LM, "--grade", man, f"--input={inp}", f"--expected={exp}"],
                       capture_output=True, text=True)
    o = json.loads(p.stdout)
    if o.get("status") != "pass":
        bad += 1
    print(f"{name:12s} {o.get('status')} {o.get('settleTick')} {o.get('reason','')}")
print("FAILURES", bad)
