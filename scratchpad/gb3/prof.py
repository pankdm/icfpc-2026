#!/usr/bin/env python3
"""prof.py <man> [--profile] — per-case settle ticks (and optional profile) for gradebook."""
import json, subprocess, sys, os
REPO = "/Users/visenbaev/icfpc26"
os.chdir(REPO)
LM = "interp/target/release/lm"
man = sys.argv[1]
prof = "--profile" in sys.argv
casefile = "tests/gradebook.json"
for a in sys.argv[2:]:
    if a.startswith("--cases="):
        casefile = a.split("=", 1)[1]
d = json.load(open(casefile))
cases = d.get("publicTestData") or d.get("cases")
tot = 0
for c in cases:
    rs = c.get("rounds") or [c]
    inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
    exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
    cmd = [LM, "--grade", man, f"--input={inp}", f"--expected={exp}", "--cap=3000000"]
    if prof:
        cmd[1] = "--profile"
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        o = json.loads(p.stdout.strip().split("\n")[-1] if not prof else p.stdout.strip().split("\n")[0])
    except Exception:
        print(c.get("name"), "ERR", p.stdout[:200], p.stderr[:200]); continue
    t = o.get("settleTick")
    tot += t or 0
    print(f"{c.get('name')[:34]:36s} {o.get('status'):8s} {t}")
    if prof:
        print(p.stdout[len(json.dumps(o)):][:3000])
print("avg", tot / len(cases))
