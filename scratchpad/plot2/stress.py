#!/usr/bin/env python3
"""20-round stress case (the spec's max) + edge shapes, graded via lm."""
import json, os, subprocess, sys
HERE = "/Users/visenbaev/icfpc26"
sys.path.insert(0, HERE + "/solutions/plotter")
from swar_ops import reference

def frame(px):
    f = [[0] * 32 for _ in range(24)]
    for a in px:
        f[a // 32][a % 32] = 15
    return ["".join("%x" % v for v in row) for row in f]

SEGS = [
    (0, 0, 0, 0), (31, 23, 31, 23), (0, 0, 31, 23), (31, 23, 0, 0),
    (0, 23, 31, 0), (31, 0, 0, 23), (0, 0, 31, 0), (31, 0, 0, 0),
    (0, 0, 0, 23), (0, 23, 0, 0), (5, 5, 26, 6), (26, 6, 5, 5),
    (5, 5, 6, 20), (6, 20, 5, 5), (16, 12, 17, 12), (17, 12, 16, 12),
    (16, 12, 16, 13), (16, 13, 16, 12), (0, 0, 1, 23), (31, 23, 30, 0),
]
rounds = []
for s in SEGS:
    rounds.append({"in": [str(v) for v in s], "out": [], "frames": [frame(reference(*s))]})

case = {"name": "stress20", "rounds": rounds}
open("/tmp/plotter_stress.json", "w").write(json.dumps({"publicTestData": [case], "tickCap": 5000000}))

man = sys.argv[1]
inp = " / ".join(" ".join(r["in"]) for r in rounds)
frames = json.dumps([r["frames"] for r in rounds])
r = subprocess.run([HERE + "/interp/target/release/lm", "--grade", man,
                    "--input=" + inp, "--expected=", "--frames=" + frames, "--cap=5000000"],
                   capture_output=True, text=True)
print(man, r.stdout.strip()[:200] or r.stderr[:200])
