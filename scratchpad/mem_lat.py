#!/usr/bin/env python3
"""Latency of a single read as a function of address (is the ladder walk visible?)."""
import json
import subprocess
import sys

MAN = sys.argv[1] if len(sys.argv) > 1 else "solutions/memory/direct-straight.man"
LM = "interp/target/release/lm"


def run(t, exp):
    r = subprocess.run(
        [LM, "--grade", MAN, "--input=" + " ".join(map(str, t)),
         "--expected=" + " ".join(map(str, exp)), "--cap=400000"],
        capture_output=True, text=True, timeout=300)
    try:
        return json.loads(r.stdout.strip().split("\n")[-1])
    except Exception:
        return {"status": "ERR", "settleTick": -1}


print("single read, addr -> settleTick")
for a in [0, 1, 2, 3, 6, 12, 24, 25, 26, 49, 50, 74, 75, 76, 98, 99]:
    r = run([0, a], [0])
    print("  addr %2d  %-8s %s" % (a, r["status"], r.get("settleTick")))

print("write then read same addr")
for a in [0, 24, 99]:
    r = run([1, a, 5, 0, a], [5])
    print("  addr %2d  %-8s %s" % (a, r["status"], r.get("settleTick")))
