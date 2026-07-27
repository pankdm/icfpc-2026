#!/usr/bin/env python3
"""Apply named structural patches to the memory champion grid and grade them.

Geometry (block b at x-offset 19*b):
  left room  cols 0-5   (walls 0,5)  rows 8-68   ladder + block spawner
  pipes      cols 6-7
  right room cols 8-18  (walls 8,18) rows 15-69  cell chain + 25 cells
  parse room rows 0-3 cols 34-53, pack room rows 0-3 cols 56-71
  fanout     rows 4-7  cols 0-75

    python3 scratchpad/mem_patch.py [-o out.man] [patch ...]
"""
import json
import subprocess
import sys

BASE = "solutions/memory/direct-straight.man"

BW = 19          # block pitch in columns
NB = 4           # blocks
NC = 25          # cells per block
CELL0 = 19       # first cell row
R0 = 9           # right(cell)-room interior left column, block 0


def load(path=BASE):
    rows = open(path).read().split("\n")
    w = max(len(r) for r in rows)
    return [list(r.ljust(w)) for r in rows]


def dump(g):
    return "\n".join("".join(r).rstrip() for r in g).rstrip("\n") + "\n"


# ---------------------------------------------------------------- patches ---
def p_nochainsub(g):
    """Drop the per-cell '-' so every cell gets the same constant (timing kept)."""
    for b in range(NB):
        ox = b * BW
        for c in range(NC - 1):
            g[CELL0 + 2 * c][ox + R0 + 7] = " "


def p_chain4(g):
    """Cell spawn chain 6 -> 4 ticks (drops the '-')."""
    for b in range(NB):
        ox = b * BW
        for c in range(NC - 1):
            y = CELL0 + 2 * c
            g[y][ox + R0 + 7] = "v"
            g[y + 1][ox + R0 + 7] = "<"


def p_blockloop(g, k=1):
    """Block header spawner loop: 2k+2 ticks (default 8 -> 4)."""
    for b in range(NB):
        ox = b * BW
        g[9][ox + 1 + k] = "v"
        g[10][ox + 1 + k] = "<"


def p_parseloop(g, k=1):
    """Parse-room spawner loop: 2k+2 ticks (default 8 -> 4)."""
    g[1][45 - k] = "v"
    g[2][45 - k] = ">"


def p_fanloop(g, k=1):
    """Fanout spawner loop: 2k+2 ticks."""
    g[5][71 + k] = "v"
    g[6][71 + k] = "<"


def p_packloop(g, k=1):
    """Pack-room spawner loop: 2k+2 ticks."""
    g[1][68 + k] = "v"
    g[2][68 + k] = "<"


def p_parseU(g):
    """Parse write branch: '<' then 'r' -> 'U' (receive+turn), read @6 not @7."""
    g[2][50] = "U"
    g[2][49] = " "
    g[2][48] = " "
    g[2][51] = "-"
    g[2][52] = "s"
    g[2][53] = "H"


def p_moveI(g, left=29):
    """Move the I room east so the input pipe is 2 cells instead of 31."""
    for y in (1, 2, 3):
        for x in range(0, 34):
            g[y][x] = " "
    g[1][left] = "+"; g[1][left + 1] = "-"; g[1][left + 2] = "+"
    g[2][left] = "|"; g[2][left + 1] = "I"; g[2][left + 2] = "|"
    g[3][left] = "+"; g[3][left + 1] = "-"; g[3][left + 2] = "+"
    for x in range(left + 3, 34):
        g[2][x] = ">"


def p_trim(g, ncell=13):
    """Keep only `ncell` cells per block (probe: how much init is the chain?).

    Deletes whole 4-row ladder units from the middle so rungs stay aligned.
    Addresses with idx >= ncell break -- probe only."""
    keep = ncell - 1                      # cells kept above the deleted span
    y0 = 19 + 2 * keep
    y1 = 67                               # first row of the final cell
    ndel = y1 - y0
    assert ndel % 4 == 0, ndel
    del g[y0:y1]


PATCHES = {k[2:]: v for k, v in sorted(globals().items()) if k.startswith("p_")}


# ----------------------------------------------------------------- grading --
def grade(path):
    try:
        r = subprocess.run(["python3", "tools/grade_fast.py", "memory", path],
                           capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return {"passed": -1, "total": "TO"}
    try:
        return json.loads(r.stdout.strip().split("\n")[-1])
    except Exception:
        return {"passed": -1, "total": "ERR", "err": (r.stdout + r.stderr)[-160:]}


def apply(g, spec):
    name, _, arg = spec.partition("=")
    if arg:
        PATCHES[name](g, int(arg))
    else:
        PATCHES[name](g)


def main():
    args = list(sys.argv[1:])
    out = None
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1]
        del args[i:i + 2]
    for a in args:
        if a.partition("=")[0] not in PATCHES:
            print("unknown:", a, "\navailable:", " ".join(PATCHES))
            return
    g = load()
    for a in args:
        apply(g, a)
    path = out or "/tmp/mem_patch.man"
    open(path, "w").write(dump(g))
    r = grade(path)
    fp = r.get("footprint", {})
    ticks = [c.get("settleTick") for c in r.get("results", [])]
    print("%-46s pass=%s/%s box=%s avg=%.1f score=%.0f %s" % (
        " ".join(args) or "(base)", r.get("passed"), r.get("total"),
        fp.get("box"), r.get("avgTicks") or -1, r.get("score") or -1, ticks))


main()
