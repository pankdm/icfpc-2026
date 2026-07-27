#!/usr/bin/env python3
"""Profile one public case of a .man with the rust engine."""
import json, subprocess, sys, os
ROOT = "/Users/visenbaev/icfpc26"
LM = ROOT + "/interp/target/release/lm"
slug = sys.argv[1]
man = sys.argv[2]
which = sys.argv[3] if len(sys.argv) > 3 else None
spec = json.load(open(f"{ROOT}/tests/{slug}.json"))
for t in spec["publicTestData"]:
    if which and which not in t["name"]:
        continue
    inp = " / ".join(" ".join(r["in"]) for r in t["rounds"])
    exp = " / ".join(" ".join(r["out"]) for r in t["rounds"])
    p = subprocess.run([LM, "--profile", man, f"--input={inp}", f"--expected={exp}"],
                       capture_output=True, text=True)
    print(t["name"], p.stdout.strip())
    print(p.stderr.strip()[:1500])
