#!/usr/bin/env python3
"""Visit count + gap histogram for one cell, from an lm --trace.

  python3 scratchpad/gbrelayout/cyc.py <man> <x> <y> [case-index]
"""
import collections, json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
man, cx, cy = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
idx = int(sys.argv[4]) if len(sys.argv) > 4 else -1

spec = json.load(open(os.path.join(REPO, "tests", "gradebook.json")))
tc = spec["publicTestData"][idx]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.run([LM, man, "--trace", f"--input={inp}", f"--expected={exp}", "--cap=5000000"],
                   capture_output=True, text=True)
seq = [tuple(map(int, l.split()))[1:] for l in (p.stdout or "").splitlines()]
ts = [t for t, c in enumerate(seq) if c == (cx, cy)]
print("ticks", len(seq), "visits to (%d,%d):" % (cx, cy), len(ts))
g = collections.Counter(ts[i + 1] - ts[i] for i in range(len(ts) - 1))
print("gaps:", g.most_common(10))
