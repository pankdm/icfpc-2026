"""Per-cell tick attribution restricted to one room, with the glyph shown.

`lm --profile` writes PROFILE cells=[...] to stderr. What matters for ACC is
which of its cells the man burns ticks on WITHOUT computing: blanks and
direction glyphs are pure walk tax, and ACC's control excursion runs once per
output element rather than once per MAC.

    python3 scratchpad/mm2/acc_prof.py <file.man> <case> <x0> <y0> <w> <h>
"""
import ast
import json
import re
import subprocess
import sys

MAN = sys.argv[1]
CASE = int(sys.argv[2])
BOX = [int(v) for v in sys.argv[3:7]] if len(sys.argv) > 6 else None


def case_io(idx):
    d = json.load(open("tests/matmul.json"))
    td = d["publicTestData"][idx]
    if "rounds" in td:
        ti, to = [], []
        for r in td["rounds"]:
            ti += [str(x) for x in r["in"]]
            to += [str(x) for x in r.get("out", [])]
        return " ".join(ti), " ".join(to), td.get("name", "")
    return (" ".join(str(x) for x in td["in"]),
            " ".join(str(x) for x in td["out"]), td.get("name", ""))


inp, exp, name = case_io(CASE)
r = subprocess.run(["interp/target/release/lm", "--profile", MAN,
                    f"--input={inp}", f"--expected={exp}", "--cap=5000000"],
                   capture_output=True, text=True, timeout=900)
print(r.stdout.strip(), file=sys.stderr)

grid = [l.rstrip('\n') for l in open(MAN)]
def gl(x, y):
    return grid[y][x] if 0 <= y < len(grid) and 0 <= x < len(grid[y]) else ' '

cells = ast.literal_eval(re.search(r'PROFILE cells=(\[.*?\])\n', r.stderr, re.S).group(1))
stalls = dict(ast.literal_eval(re.search(r'PROFILE stalls=(\[.*?\])\n?$', r.stderr, re.S).group(1)))
tot = sum(n for _, n in cells)
print(f'total cell-ticks {tot}')

if BOX:
    x0, y0, w, h = BOX
    sel = [(c, n) for c, n in cells if x0 <= c[0] < x0 + w and y0 <= c[1] < y0 + h]
    sub = sum(n for _, n in sel)
    print(f'room box ({x0},{y0}) {w}x{h}: {sub} ticks = {100*sub/tot:.1f}% of all')
    waste = sum(n for c, n in sel if gl(*c) in ' .<>^v')
    print(f'   walk tax (blank + direction glyphs): {waste} = {100*waste/sub:.1f}% of room')
    for c, n in sorted(sel, key=lambda t: -t[1])[:28]:
        ch = gl(*c)
        tag = 'WALK' if ch in ' .<>^v' else 'op  '
        st = stalls.get(c, 0)
        print(f'   {c} {ch!r} {tag} {n:7d}' + (f'  stall {st}' if st else ''))
