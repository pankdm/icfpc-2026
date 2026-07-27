#!/usr/bin/env python3
"""Random multi-round fuzz of a sort-numbers .man against the rust engine."""
import json, random, subprocess, sys
ROOT = "/Users/visenbaev/icfpc26"
LM = ROOT + "/interp/target/release/lm"
man = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 120
random.seed(int(sys.argv[3]) if len(sys.argv) > 3 else 1)

bad = 0
for i in range(N):
    nrounds = random.randint(2, 6)
    rounds = []
    for _ in range(nrounds):
        n = random.randint(1, 16)
        style = random.choice(["rand", "asc", "desc", "equal", "narrow", "extreme"])
        if style == "rand":
            r = [random.randint(-10000, 10000) for _ in range(n)]
        elif style == "asc":
            r = sorted(random.randint(-10000, 10000) for _ in range(n))
        elif style == "desc":
            r = sorted((random.randint(-10000, 10000) for _ in range(n)), reverse=True)
        elif style == "equal":
            r = [random.randint(-10000, 10000)] * n
        elif style == "narrow":
            r = [random.randint(-2, 2) for _ in range(n)]
        else:
            r = [random.choice([-10000, 10000, 0]) for _ in range(n)]
        rounds.append(r)
    inp = " / ".join(" ".join([str(len(r))] + [str(v) for v in r]) for r in rounds)
    exp = " / ".join(" ".join(str(v) for v in sorted(r)) for r in rounds)
    p = subprocess.run([LM, "--grade", man, f"--input={inp}", f"--expected={exp}"],
                       capture_output=True, text=True)
    o = json.loads(p.stdout)
    if o.get("status") != "pass":
        bad += 1
        print("FAIL", o, inp[:200])
print(f"{N - bad}/{N} pass")
