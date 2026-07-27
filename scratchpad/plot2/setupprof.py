#!/usr/bin/env python3
"""Where do plotter's 326 ticks/round of SETUP go?

`one pixel` is 97% setup (336 ticks, 1 round, 1 pixel), so profiling it isolates
the per-round constant almost perfectly.  `lm --profile` writes its data to
STDERR in Rust debug format (`PROFILE cells=[((x, y), n), ...]`), so parse that.

    python3 scratchpad/plot2/setupprof.py ["case name"]
"""
import json
import re
import subprocess
import sys
from collections import defaultdict

MAN = "solutions/plotter/plotter-swar8.man"
CASE = sys.argv[1] if len(sys.argv) > 1 else "one pixel"

spec = json.load(open("tests/plotter.json"))
case = [t for t in spec["publicTestData"] if t["name"] == CASE][0]
open("/tmp/plot_frames.json", "w").write(json.dumps(case["rounds"]))

r = subprocess.run(
    ["interp/target/release/lm", "--profile", MAN,
     "--frames-file=/tmp/plot_frames.json", "--cap=340"],
    capture_output=True, text=True, timeout=300)

print(r.stdout.strip()[:200])
err = r.stderr

PAIR = re.compile(r"\(\((-?\d+), (-?\d+)\), (\d+)\)")
GLYPH = re.compile(r"\('(.)', (\d+)\)")


def section(name):
    m = re.search(r"PROFILE %s=(\[.*?\])\n" % name, err, re.S)
    return m.group(1) if m else ""


cells = [(int(x), int(y), int(n)) for x, y, n in PAIR.findall(section("cells"))]
stalls = [(int(x), int(y), int(n)) for x, y, n in PAIR.findall(section("stalls"))]
glyphs = [(g, int(n)) for g, n in GLYPH.findall(section("glyphs"))]
mstall = re.search(r"PROFILE stall_total=(\d+)", err)

grid = open(MAN).read().split("\n")
exec_total = sum(n for _, _, n in cells)
stall_total = int(mstall.group(1)) if mstall else 0

print("case=%s   exec=%d  stall=%d  sum=%d"
      % (CASE, exec_total, stall_total, exec_total + stall_total))

print("\ntop glyphs:", glyphs[:12])

rows = defaultdict(int)
for x, y, n in cells:
    rows[y] += n
print("\nexec ticks by row (top 12):")
for y, t in sorted(rows.items(), key=lambda kv: -kv[1])[:12]:
    line = grid[y] if y < len(grid) else ""
    print("  row %2d  %5d  %5.1f%%  %s" % (y, t, 100.0 * t / exec_total,
                                           line[:54]))

print("\nhottest cells (top 15):")
for x, y, n in cells[:15]:
    ch = grid[y][x] if y < len(grid) and x < len(grid[y]) else "?"
    print("  (%2d,%2d) '%s'  %4d" % (x, y, ch, n))

if stalls:
    print("\ntop stall cells:")
    for x, y, n in stalls[:10]:
        ch = grid[y][x] if y < len(grid) and x < len(grid[y]) else "?"
        print("  (%2d,%2d) '%s'  %4d" % (x, y, ch, n))
