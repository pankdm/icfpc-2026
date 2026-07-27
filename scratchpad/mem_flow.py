#!/usr/bin/env python3
"""Log every value that crosses each front-end pipe, tick by tick.

Reconstructs the stream per pipe by diffing --inspect snapshots: a value that
appears at the pipe's source end is one that was just sent.
"""
import json
import subprocess
import sys

MAN = sys.argv[1]
INP = sys.argv[2] if len(sys.argv) > 2 else "0 3 0 4 0 5"
T1 = int(sys.argv[3]) if len(sys.argv) > 3 else 260
WATCH = [(3, 2), (26, 2), (41, 2), (56, 2), (6, 8)]   # pipe src cells to watch


def snap(t):
    r = subprocess.run(["interp/target/release/lm", MAN, "--input=" + INP,
                        "--inspect=%d" % t, "--cap=%d" % (t + 2)],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().split("\n")[-1])
    except Exception:
        return None


seen = {}
for t in range(0, T1):
    d = snap(t)
    if d is None:
        print("no snapshot at", t)
        break
    for p in d["pipes"]:
        src = tuple(p["src"])
        if src not in WATCH:
            continue
        vals = p.get("values")
        if not vals:
            continue
        head = vals[0]
        key = (src, t)
        prev = seen.get(src)
        if head is not None and head != prev:
            print("t=%4d pipe %-9s <- %s" % (t, src, head))
        seen[src] = head
