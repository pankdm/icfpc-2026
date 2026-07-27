#!/usr/bin/env python3
"""Per-row tick attribution of room0 summed over all PUBLIC cases."""
import ast, json, re, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = f"{REPO}/interp/target/release/lm"
man = sys.argv[1]
spec = json.load(open(f"{REPO}/tests/gradebook.json"))
rows_txt = open(man).read().split("\n")
agg, tot = {}, 0
for c in spec["publicTestData"]:
    inp = " ".join(" ".join(r["in"]) for r in c["rounds"])
    exp = " ".join(" ".join(r["out"]) for r in c["rounds"])
    p = subprocess.run([LM, "--profile", man, f"--input={inp}", f"--expected={exp}",
                        "--cap=5000000"], capture_output=True, text=True)
    st = json.loads(p.stdout.strip().splitlines()[-1])
    tot += st.get("settleTick", 0)
    m = re.search(r"PROFILE cells=(\[.*?\])\nPROFILE stall", p.stderr, re.S)
    for (x, y), n in ast.literal_eval(m.group(1)):
        if y <= 64:
            agg[y] = agg.get(y, 0) + n
print(f"total public ticks = {tot}")
for y, n in sorted(agg.items(), key=lambda kv: -kv[1])[:26]:
    print(f"row {y:3d} {n:7d} {100*n/tot:5.1f}%  |{rows_txt[y][1:38]}|")
