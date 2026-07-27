#!/usr/bin/env python3
"""Profile a memory build on the dominant case; report stalls/cells by region."""
import ast
import json
import subprocess
import sys

MAN = sys.argv[1] if len(sys.argv) > 1 else "solutions/memory/direct-straight.man"
CASE = int(sys.argv[2]) if len(sys.argv) > 2 else 6

d = json.load(open("tests/memory.json"))
c = d["publicTestData"][CASE]
out = subprocess.run(
    ["interp/target/release/lm", "--profile", MAN,
     "--input=" + " ".join(c["in"]),
     "--expected=" + " ".join(c["out"]),
     "--cap=300000"], capture_output=True, text=True)
out = out.stdout + "\n" + out.stderr

grid = [l for l in open(MAN).read().split("\n")]


def glyph(x, y):
    return grid[y][x] if y < len(grid) and x < len(grid[y]) else " "


sect = {}
for line in out.split("\n"):
    if line.startswith("PROFILE "):
        rest = line[8:]
        k, sep, v = rest.partition("=")
        if not sep:
            k, sep, v = rest.partition(" ")
        sect[k.strip()] = v
    elif line.startswith("{"):
        print(json.loads(line))

stalls = ast.literal_eval(sect["stalls"])
cells = ast.literal_eval(sect["cells"])

print("stall_total", sect.get("stall_total"))
print("\n=== TOP CELLS (ticks spent) outside memory-cell rows 8..69 ===")
sel = [(n, x, y) for (x, y), n in cells if not (8 <= y <= 69)]
sel.sort(reverse=True)
for n, x, y in sel[:35]:
    print(f"  {n:7d}  ({x:3d},{y:2d}) '{glyph(x,y)}'")

print("\n=== TOP STALLS outside memory-cell rows 8..69 ===")
sel = [(n, x, y) for (x, y), n in stalls if not (8 <= y <= 69)]
sel.sort(reverse=True)
for n, x, y in sel[:35]:
    print(f"  {n:7d}  ({x:3d},{y:2d}) '{glyph(x,y)}'")

print("\n=== TOP CELLS inside blocks (rows 8..69) ===")
sel = [(n, x, y) for (x, y), n in cells if 8 <= y <= 69]
sel.sort(reverse=True)
for n, x, y in sel[:25]:
    print(f"  {n:7d}  ({x:3d},{y:2d}) '{glyph(x,y)}'")
