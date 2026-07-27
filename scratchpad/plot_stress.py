#!/usr/bin/env python3
"""Stress the plotter build on shapes the six public cases do not cover:
degenerate segments, both traversal orders of every octant, display corners,
maximum-length lines, and long multi-round runs.  Expected frames come from
swar_ops.reference(), i.e. the assignment's own pseudocode."""
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "solutions", "plotter"))
from swar_ops import reference  # noqa: E402

LM = os.path.join(REPO, "interp", "target", "release", "lm")
MAN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    REPO, "solutions", "plotter", "plotter-swar1.man")
W, H = 32, 24


def frame(seg):
    px = set(reference(*seg))
    return ["".join("f" if y * W + x in px else "0" for x in range(W)) for y in range(H)]


def group(name, segs):
    return (name, segs)


groups = []
groups.append(group("degenerate", [(0, 0, 0, 0), (31, 23, 31, 23), (5, 7, 5, 7),
                                   (0, 23, 0, 23), (31, 0, 31, 0)]))
groups.append(group("horizontal", [(0, 5, 31, 5), (31, 5, 0, 5), (3, 0, 28, 0),
                                   (28, 23, 3, 23), (10, 12, 11, 12), (11, 12, 10, 12)]))
groups.append(group("vertical", [(7, 0, 7, 23), (7, 23, 7, 0), (0, 0, 0, 23),
                                 (31, 23, 31, 0), (4, 9, 4, 10), (4, 10, 4, 9)]))
groups.append(group("corners", [(0, 0, 31, 23), (31, 23, 0, 0), (31, 0, 0, 23),
                                (0, 23, 31, 0), (0, 0, 31, 0), (0, 0, 0, 23)]))
groups.append(group("diagonals45", [(0, 0, 23, 23), (23, 23, 0, 0), (0, 23, 23, 0),
                                    (23, 0, 0, 23), (10, 10, 11, 11), (11, 11, 10, 10)]))
octs = []
for dx, dy in [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]:
    for k in (3, 7):
        x0, y0 = 15, 11
        octs.append((x0, y0, x0 + dx * k, y0 + dy * k * (1 if abs(dy) else 1)))
        octs.append((x0 + dx * k, y0 + dy * k, x0, y0))
groups.append(group("octants both ways", octs))
rnd = random.Random(20260727)
groups.append(group("random 20-round",
                    [(rnd.randrange(W), rnd.randrange(H), rnd.randrange(W), rnd.randrange(H))
                     for _ in range(20)]))
groups.append(group("shallow/steep", [(0, 11, 31, 12), (31, 12, 0, 11), (15, 0, 16, 23),
                                      (16, 23, 15, 0), (0, 0, 31, 1), (0, 0, 1, 23)]))

bad = 0
for name, segs in groups:
    inp = " / ".join(" ".join(str(v) for v in s) for s in segs)
    frames = json.dumps([[frame(s)] for s in segs])
    r = subprocess.run([LM, "--grade", MAN, f"--input={inp}", "--expected=",
                        f"--frames={frames}", "--cap=4000000"],
                       capture_output=True, text=True, timeout=900)
    try:
        v = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        v = {"status": "engine-error", "reason": (r.stderr or r.stdout)[:200]}
    ok = v.get("status") == "pass"
    bad += 0 if ok else 1
    print(f"{name:22s} {len(segs):3d} rounds  {v.get('status')}"
          f"  tick {v.get('settleTick')}  {v.get('reason', '')}")
print("FAILED GROUPS:", bad)
