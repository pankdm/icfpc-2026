#!/usr/bin/env python3
"""Profile one public case of gradebook with the Rust engine.

  python3 scratchpad/gbrelayout/prof.py <man> [case-index] [top-n]
"""
import json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

man = sys.argv[1]
idx = int(sys.argv[2]) if len(sys.argv) > 2 else -1
topn = int(sys.argv[3]) if len(sys.argv) > 3 else 40

spec = json.load(open(os.path.join(REPO, "tests", "gradebook.json")))
tc = spec["publicTestData"][idx]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.run([LM, "--profile", man, f"--input={inp}", f"--expected={exp}", "--cap=5000000"],
                   capture_output=True, text=True)
out = (p.stdout or "") + (p.stderr or "")
print(out[:6000])
