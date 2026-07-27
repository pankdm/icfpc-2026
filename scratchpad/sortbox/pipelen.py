#!/usr/bin/env python3
"""Minimum length of the ring-return pipe (pipe2) for ring15-v2.

The merged read loop consumes one ring value during pass 1, so peak ring occupancy at a `q`
should be n-1 = 15, not 16.  Three traps make this hard to test by hand:

  * PARITY -- a simple path between two fixed cells exists only for one parity of length,
    so length 15 is unreachable with pipe2's current endpoints; use a different wall cell.
  * FALSE STARTS -- the loader treats ANY arrow whose backward neighbour is a room border as
    a pipe start.  A mid-pipe cell sitting against a wall and pointing away from it is traced
    as its own pipe, and if it happens to end at the same room you get `pipe self-loop`.
  * dense serpentines are otherwise fine (the shipped build is one).

usage: python3 scratchpad/sortbox/pipelen.py
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = open(os.path.join(REPO, "solutions", "sort-numbers", "ring15-v2.man")).read()

OLD = [(13, 9), (13, 8), (14, 8), (14, 7), (13, 7), (12, 7), (11, 7),
       (11, 6), (12, 6), (13, 6), (14, 6), (14, 5), (13, 5), (12, 5),
       (11, 5), (10, 5)]
START = (13, 9)

ROWS0 = [list(r) for r in BASE.split("\n")]
WID = max(len(r) for r in ROWS0)
for r in ROWS0:
    r.extend(" " * (WID - len(r)))
BORDER = {(x, y) for y, r in enumerate(ROWS0) for x, c in enumerate(r) if c in "+-|"}

FREE = {(x, y) for x in range(10, 15) for y in range(3, 10)}
FREE -= {(12, 3), (13, 3), (14, 3)}           # under the input room
FREE -= {(10, 9), (11, 9), (12, 9), (14, 9)}  # beside the relay's top wall

DIRC = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}


def legal(path, wall):
    """no mid-pipe cell may point directly away from a room border (false pipe start)"""
    full = path + [wall]
    for i in range(1, len(full) - 1):
        x, y = full[i]
        dx, dy = full[i + 1][0] - x, full[i + 1][1] - y
        if (x - dx, y - dy) in BORDER:
            return False
    return True


def paths(end, wall, n, cap=8):
    out = []

    def go(cur, seen):
        if len(out) >= cap:
            return
        if len(seen) == n:
            if cur == end and legal(seen, wall):
                out.append(list(seen))
            return
        x, y = cur
        for nx, ny in ((x, y - 1), (x + 1, y), (x - 1, y), (x, y + 1)):
            if (nx, ny) in FREE and (nx, ny) not in seen:
                seen.append((nx, ny))
                go((nx, ny), seen)
                seen.pop()

    go(START, [START])
    return out


def render(path, wall):
    rows = [r[:] for r in ROWS0]
    for x, y in OLD:
        rows[y][x] = " "
    full = path + [wall]
    for i in range(len(full) - 1):
        x, y = full[i]
        rows[y][x] = DIRC[(full[i + 1][0] - x, full[i + 1][1] - y)]
    return "\n".join("".join(r).rstrip() for r in rows) + "\n"


def grade(path, slug, wall):
    open("/tmp/plen.man", "w").write(render(path, wall))
    r = subprocess.run([sys.executable, "tools/grade_fast.py", slug, "/tmp/plen.man", "--jobs", "8"],
                       cwd=REPO, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


for end, wall in (((10, 5), (9, 5)), ((10, 6), (9, 6))):
    for n in range(11, 17):
        cands = paths(end, wall, n)
        if not cands:
            print(f"end {end} len {n}: no legal path")
            continue
        for c in cands:
            d = grade(c, "sort-numbers", wall)
            if d and d["passed"] == d["total"]:
                s = grade(c, "sort-stress", wall)
                print(f"end {end} len {n}: public PASS, stress {s['passed']}/{s['total']}")
                break
            reason = (d or {}).get("results", [{}])[0].get("reason") or "cases fail"
        else:
            print(f"end {end} len {n}: {len(cands)} legal paths, none pass ({reason})")
