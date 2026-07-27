#!/usr/bin/env python3
"""Randomised multi-round fuzz for sort-numbers builds."""
import random
import subprocess
import sys

LM = "/Users/visenbaev/icfpc26/interp/target/release/lm"
path = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
rng = random.Random(seed)

cases = []
# edge cases first
cases.append([[1, 3], [1, -3], [1, 0]])
cases.append([[1, 0]])
cases.append([[1, -10000], [1, 10000]])
cases.append([[16] + [7] * 16])
cases.append([[16] + list(range(16, 0, -1))])
cases.append([[16] + list(range(1, 17))])
cases.append([[2, 5, 5], [3, -1, -1, -1], [1, 0]])
for _ in range(N):
    rounds = []
    for _ in range(rng.randint(1, 6)):
        n = rng.randint(1, 16)
        vals = [rng.randint(-10000, 10000) for _ in range(n)]
        if rng.random() < 0.4:
            vals = [rng.choice([-1, 0, 1, 5]) for _ in range(n)]
        rounds.append([n] + vals)
    cases.append(rounds)

bad = 0
for ci, rounds in enumerate(cases):
    inp = " / ".join(" ".join(str(v) for v in r) for r in rounds)
    exp = " / ".join(" ".join(str(v) for v in sorted(r[1:])) for r in rounds)
    out = subprocess.run([LM, "--grade", path, "--input=" + inp, "--expected=" + exp,
                          "--cap=400000"], capture_output=True, text=True)
    last = (out.stdout + out.stderr).strip()
    if '"settleTick"' not in last or '"status":"pass"' not in last:
        bad += 1
        if bad <= 3:
            print("FAIL case", ci, "in=", inp[:90])
            print("   ", last[:200])
print("cases", len(cases), "failures", bad)
