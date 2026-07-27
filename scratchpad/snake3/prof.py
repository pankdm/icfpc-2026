"""Attribute the controller man's ticks to columns/rows, split op vs blank vs arrow."""
import ast, json, os, subprocess, sys

REPO = "/Users/dmitrykorolev/projects/icfpc-2026-main"
sys.path.insert(0, REPO + "/tools")
import grade_fast as gf

MAN = sys.argv[1] if len(sys.argv) > 1 else REPO + "/solutions/snake/fold14.man"
CASE = sys.argv[2] if len(sys.argv) > 2 else "long"

spec = json.load(open(REPO + "/tests/snake.json"))
tc = [c for c in spec["publicTestData"] if CASE in c["name"].lower()][0]
inp, exp, frames = gf.rounds_of(tc)
open("/tmp/pf.json", "w").write(frames)
p = subprocess.run([REPO + "/interp/target/release/lm", "--profile", MAN,
                    "--input=" + inp, "--expected=" + exp,
                    "--frames-file=/tmp/pf.json", "--cap=60000"],
                   capture_output=True, text=True)
cells = stalls = None
for line in (p.stdout + "\n" + p.stderr).splitlines():
    if line.startswith("PROFILE cells="):
        cells = dict(ast.literal_eval(line[len("PROFILE cells="):]))
    if line.startswith("PROFILE stalls="):
        stalls = dict(ast.literal_eval(line[len("PROFILE stalls="):]))

grid = [l.rstrip("\n") for l in open(MAN)]
def g(x, y):
    return grid[y][x] if y < len(grid) and x < len(grid[y]) else " "

# controller room = the one with the most visited cells; identify by bounding the
# heavy region.  Just report per-column and per-row totals over the whole grid,
# split by glyph class.
ARROWS = set("<>^v")
percol, perrow = {}, {}
cls_tot = {}
for (x, y), n in cells.items():
    ch = g(x, y)
    k = "blank" if ch == " " else ("arrow" if ch in ARROWS else "op")
    cls_tot[k] = cls_tot.get(k, 0) + n
    percol.setdefault(x, {}).setdefault(k, 0)
    percol[x][k] += n
    perrow.setdefault(y, {}).setdefault(k, 0)
    perrow[y][k] += n

tot = sum(cells.values())
print("MAN", MAN, "case", tc["name"])
print("total visited-cell ticks", tot, cls_tot,
      "stall", sum(stalls.values()) if stalls else 0)
print("\n-- columns by blank+arrow cost --")
for x, d in sorted(percol.items(), key=lambda kv: -(kv[1].get("blank", 0) + kv[1].get("arrow", 0)))[:16]:
    print("  col %3d blank %6d arrow %5d op %6d" %
          (x, d.get("blank", 0), d.get("arrow", 0), d.get("op", 0)))
print("\n-- rows by blank+arrow cost --")
for y, d in sorted(perrow.items(), key=lambda kv: -(kv[1].get("blank", 0) + kv[1].get("arrow", 0)))[:16]:
    print("  row %3d blank %6d arrow %5d op %6d" %
          (y, d.get("blank", 0), d.get("arrow", 0), d.get("op", 0)))
