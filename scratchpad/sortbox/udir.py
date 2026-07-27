#!/usr/bin/env python3
"""Which direction does `U` face after receiving -- the pipe's END ARROWHEAD, or the last
step INSIDE its path?  They differ whenever a pipe turns on its final cell.

interp/src/lib.rs computes `path[-1] - path[-2]` (the last step) despite a comment claiming
the arrowhead.  If the reference oracle uses the arrowhead instead, a relay room fed by a
2-cell L-pipe deadlocks on one engine and runs on the other.

Builds the 14x14 relay both ways and grades each on BOTH engines.

usage: python3 scratchpad/sortbox/udir.py
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.join(REPO, "scratchpad", "sortbox", "build14d.py")
SRC = open(BUILD).read()

SOUTH = """cells({
    (6, 11): "U", (6, 12): ">", (7, 12): "s",
    (8, 12): "^", (8, 11): "<", (7, 11): "@",
})"""
EAST = """cells({
    (6, 11): "U", (7, 11): "s", (8, 11): "v",
    (8, 12): "<", (7, 12): "@", (6, 12): "^",
})"""

for name, block in (("relay oriented for SOUTH (rust's last-step rule)", SOUTH),
                    ("relay oriented for EAST  (arrowhead rule)", EAST)):
    src = SRC.replace(SOUTH, block)
    tmp = "/tmp/udir_build.py"
    open(tmp, "w").write(src)
    man = "/tmp/udir.man"
    subprocess.run([sys.executable, tmp, man], cwd=REPO, check=True)

    r = subprocess.run([sys.executable, "tools/grade_fast.py", "sort-numbers", man],
                       cwd=REPO, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        rust = f"{d['passed']}/{d['total']}"
    except Exception:
        rust = "error"

    o = subprocess.run(["node", "tools/grade.js", "sort-numbers", man],
                       cwd=REPO, capture_output=True, text=True)
    m = re.search(r"(\d+)/(\d+) public", o.stdout)
    oracle = f"{m.group(1)}/{m.group(2)}" if m else "error"

    print(f"{name}:  rust {rust}   oracle {oracle}")
