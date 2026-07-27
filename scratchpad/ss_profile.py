#!/usr/bin/env python3
"""Profile a subset-sum .man on one public case with the Rust engine.

usage: python3 scratchpad/ss_profile.py <file.man> [case_index]
Prints: verdict, stall total, top glyphs, and the hottest cells grouped by
(x mod stride) so a repeated worker tile shows up as one hot loop.
"""
import ast
import json
import os
import subprocess
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LM = os.path.join(REPO, "interp", "target", "release", "lm")


def main():
    path = sys.argv[1]
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    spec = json.load(open(os.path.join(REPO, "tests", "subset-sum.json")))
    tc = spec["publicTestData"][idx]
    rs = tc.get("rounds") or [tc]
    inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
    exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
    p = subprocess.run(
        [LM, "--profile", path, f"--input={inp}", f"--expected={exp}", "--cap=15000000"],
        capture_output=True, text=True,
    )
    print("VERDICT", p.stdout.strip())
    glyphs = rooms = cells = stalls = None
    stall_total = 0
    for line in p.stderr.splitlines():
        if line.startswith("PROFILE glyphs="):
            glyphs = ast.literal_eval(line.split("=", 1)[1])
        elif line.startswith("PROFILE rooms="):
            rooms = ast.literal_eval(line.split("=", 1)[1])
        elif line.startswith("PROFILE stall_total="):
            stall_total = int(line.split("=", 1)[1])
        elif line.startswith("PROFILE cells="):
            cells = ast.literal_eval(line.split("=", 1)[1])
        elif line.startswith("PROFILE stalls="):
            stalls = ast.literal_eval(line.split("=", 1)[1])
    src = open(path, encoding="utf-8").read().split("\n")

    def ch(x, y):
        return src[y][x] if y < len(src) and x < len(src[y]) else " "

    total_exec = sum(c for _, c in cells) if cells else 0
    print("stall_total", stall_total, "exec_total", total_exec)
    print("glyphs", glyphs[:20] if glyphs else None)
    print("rooms(top8)", rooms[:8] if rooms else None)
    if rooms:
        hot_room = rooms[0][0]
    # hottest cells overall
    print("\nHOT CELLS (top 40):  x,y glyph count")
    for (x, y), c in (cells or [])[:40]:
        print(f"  {x:4d},{y:4d} {ch(x,y)!r} {c}")
    print("\nHOT STALLS (top 20):")
    for (x, y), c in (stalls or [])[:20]:
        print(f"  {x:4d},{y:4d} {ch(x,y)!r} {c}")


main()
