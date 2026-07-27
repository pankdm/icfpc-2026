#!/usr/bin/env python3
"""Trace a .man run: print cell executed by each man, with A/B/BP, plus pipe fill.

usage: trace.py <file.man> <steps> "<input>" [--expected=..] [--only=x,y] [--from=N]
"""
import json
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
LM = REPO + "/interp/target/release/lm"

path = sys.argv[1]
steps = sys.argv[2]
inp = sys.argv[3]
extra = [a for a in sys.argv[4:] if a.startswith("--expected")]
only = None
frm = 0
for a in sys.argv[4:]:
    if a.startswith("--only="):
        only = set(tuple(int(v) for v in p.split(",")) for p in a[len("--only="):].split(";"))
    if a.startswith("--from="):
        frm = int(a[len("--from="):])

grid = [l.rstrip("\n") for l in open(path)]
def ch(x, y):
    return grid[y][x] if y < len(grid) and x < len(grid[y]) else " "

out = subprocess.run([LM, path, steps, "--input=" + inp] + extra,
                     capture_output=True, text=True).stdout
for line in out.splitlines():
    s = json.loads(line)
    if s["step"] < frm:
        continue
    parts = []
    for r in s["runners"]:
        x, y = r["pos"]
        if only and (x, y) not in only:
            continue
        parts.append("m%d@(%d,%d)%r A=%d B=%d BP=%d" % (r["id"], x, y, ch(x, y), r["a"], r["b"], r["backpack"]))
    if only and not parts:
        continue
    pipes = []
    for p in s["pipes"] or []:
        n = len(p["values"] or [])
        pipes.append("p%d:%d" % (p["id"], n))
    print("t%-5d %s | %s | out=%s" % (s["step"], "  ".join(parts), " ".join(pipes),
                                      len(s["output"] or [])))
    if s["end"] != "running":
        print("END", s["end"])
        break
