#!/usr/bin/env python3
"""Attribute each public case's ticks to row bands of room0 (AVG loop, TOP loop, rest)."""
import ast, json, re, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = f"{REPO}/interp/target/release/lm"
man = sys.argv[1]
spec = json.load(open(f"{REPO}/tests/gradebook.json"))
cases = spec["publicTestData"]

BANDS = {"AVGloop": range(35, 43), "TOPloop": range(49, 57)}
tot_all = 0
agg = {k: 0 for k in BANDS}
agg["room0_other"] = 0
for c in cases:
    inp = " ".join(r["in"] if isinstance(r["in"], str) else " ".join(r["in"])
                   for r in c["rounds"])
    exp = " ".join(r["out"] if isinstance(r["out"], str) else " ".join(r["out"])
                   for r in c["rounds"])
    p = subprocess.run([LM, "--profile", man, f"--input={inp}", f"--expected={exp}",
                        "--cap=5000000"], capture_output=True, text=True)
    st = json.loads(p.stdout.strip().splitlines()[-1])
    m = re.search(r"PROFILE cells=(\[.*?\])\nPROFILE stall", p.stderr, re.S)
    cells = ast.literal_eval(m.group(1))
    per = {k: 0 for k in BANDS}
    other = 0
    for (x, y), n in cells:
        if y > 64:
            continue
        for k, rng in BANDS.items():
            if y in rng:
                per[k] += n
                break
        else:
            other += n
    t = st.get("settleTick", 0)
    tot_all += t
    for k in BANDS:
        agg[k] += per[k]
    agg["room0_other"] += other
    print(f"{c['name'][:24]:24} ticks={t:7d} " +
          " ".join(f"{k}={per[k]:6d}" for k in BANDS) + f" other={other:6d}")
print(f"TOTAL ticks={tot_all} " + " ".join(f"{k}={agg[k]} ({100*agg[k]/tot_all:.1f}%)"
                                          for k in list(BANDS) + ["room0_other"]))
