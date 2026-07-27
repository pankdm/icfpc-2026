#!/usr/bin/env python3
"""Is direct-memory's long input pipe load-bearing, or just slack?

The I room's pipe leaves (3,2), climbs to row 0, runs east, drops to row 1,
runs WEST, drops back to row 2 and runs east to the dispatcher — roughly 53
cells where a straight run along row 2 would be ~30.  A pipe is a FIFO, so
extra cells are extra buffer; they also add latency.  Rewrite it straight and
ask the oracle.

    python3 scratchpad/dm_inpipe.py            # report the current path
    python3 scratchpad/dm_inpipe.py --straight # emit /tmp/dm_straight.man
"""
import subprocess
import sys

SRC = "/tmp/dm.man"


def load(path):
    rows = open(path).read().split("\n")
    w = max(len(r) for r in rows)
    return [list(r.ljust(w)) for r in rows], w


def show_head(g, n=4):
    for y in range(n):
        print("%2d |%s|" % (y, "".join(g[y][:60])))


def straighten(g):
    """Replace the serpentine with a straight eastward run on row 2."""
    # find where the pipe enters the dispatcher room on row 2
    # the FIRST room wall east of the I room on row 2 is the destination
    row2 = g[2]
    dest = None
    for x in range(5, len(row2) - 1):
        if row2[x] == "|":
            dest = x - 1          # arrowhead sits just west of the wall
            break
    if dest is None:
        sys.exit("could not find the row-2 destination wall")
    # blank the detour on rows 0 and 1
    for y in (0, 1):
        for x in range(3, dest + 1):
            if g[y][x] in "><^v-|":
                g[y][x] = " "
    # lay a straight run: '>' at 3, dashes, '>' at dest
    g[2][3] = ">"
    for x in range(4, dest):
        g[2][x] = "-"
    g[2][dest] = ">"
    return g, dest


def grade(path):
    out = subprocess.run(
        ["python3", "tools/grade_fast.py", "memory", path],
        capture_output=True, text=True).stdout
    return out.strip().split("\n")[-1][:240]


def main():
    g, w = load(SRC)
    print("current head:")
    show_head(g)
    if "--straight" not in sys.argv:
        return
    g, dest = straighten(g)
    print("\nstraightened (entry col %d):" % dest)
    show_head(g)
    out = "/tmp/dm_straight.man"
    open(out, "w").write("\n".join("".join(r).rstrip() for r in g))
    print("\nbaseline :", grade(SRC))
    print("straight :", grade(out))


main()
