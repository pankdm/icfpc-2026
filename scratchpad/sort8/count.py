#!/usr/bin/env python3
"""Count visits to marked cells across all public cases of a slug."""
import json
import subprocess
import sys
from collections import Counter

REPO = "/Users/visenbaev/icfpc26"
LM = REPO + "/interp/target/release/lm"

slug = sys.argv[1]
path = sys.argv[2]
marks = {}
for a in sys.argv[3:]:
    name, xy = a.split("=")
    x, y = xy.split(",")
    marks[(int(x), int(y))] = name

spec = json.load(open(f"{REPO}/tests/{slug}.json"))
total = Counter()
for tc in spec["publicTestData"]:
    rs = tc.get("rounds") or [tc]
    inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
    exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
    out = subprocess.run([LM, path, "100000", "--input=" + inp, "--expected=" + exp],
                         capture_output=True, text=True).stdout
    c = Counter()
    last = None
    for line in out.splitlines():
        s = json.loads(line)
        for r in s["runners"]:
            p = tuple(r["pos"])
            if p in marks:
                c[marks[p]] += 1
        last = s
    print("%-26s ticks=%-6s %s" % (tc["name"], last["step"], dict(c)))
    total.update(c)
print("TOTAL", dict(total))
