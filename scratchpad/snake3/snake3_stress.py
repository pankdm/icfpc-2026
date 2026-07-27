#!/usr/bin/env python3
"""Run the frozen 154-case stress set against a .man (read-only use of the other
stream's scratchpad/snake2/stress.json -- nothing there is modified).

  python3 snake3_stress.py <man>
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
man = sys.argv[1]
cases = json.load(open(os.path.join(REPO, "scratchpad", "snake2", "stress.json")))


def run(i_c):
    i, c = i_c
    ff = f"/tmp/snake3_st{i}.json"
    open(ff, "w").write(c.get("frames") or "")
    r = subprocess.run([LM, "--grade", man, f"--input={c['input']}",
                        f"--expected={c.get('expected','')}",
                        f"--frames-file={ff}", "--cap=400000"],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return c["name"], "parse"
    return c["name"], d.get("status")


bad = []
with ThreadPoolExecutor(max_workers=8) as ex:
    for name, st in ex.map(run, list(enumerate(cases))):
        if st != "pass":
            bad.append((name, st))
print(f"{len(cases) - len(bad)}/{len(cases)} pass")
for n, s in bad[:12]:
    print("  FAIL", n, s)
