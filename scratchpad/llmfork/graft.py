#!/usr/bin/env python3
"""Graft a second man into the LLM champion at the grid level."""
import sys
SRC = "solutions/little-little-man/live-2b320f4f.man"

def load():
    rows = open(SRC).read().split("\n")
    W = max(len(r) for r in rows)
    return [list(r.ljust(W)) for r in rows], W

def put(G, x, y, ch, expect=None):
    if expect is not None and G[y][x] != expect:
        raise SystemExit(f"expected {expect!r} at ({x},{y}), found {G[y][x]!r}")
    G[y][x] = ch

def save(G, path):
    open(path, "w").write("\n".join("".join(r).rstrip() for r in G))

variant = sys.argv[1]
G, W = load()

# Fork site: the entry block's drop cell.  Row 1 ends `s0sWsv` (v at x=124);
# (124,2) is the '<' that turns the man west.  A man arriving there heads SOUTH,
# so Y makes copies at (123,2) heading WEST and (125,2) heading EAST -- exactly
# the two directions we want, at ZERO tick cost for the west (original) copy.
put(G, 124, 2, "Y", "<")
put(G, 123, 2, "<", " ")     # west copy resumes the original westward walk

if variant == "s1":
    put(G, 125, 2, "H", " ")  # second man halts immediately, in a never-visited cell
elif variant == "s2":
    # widen room 0's east wall 317 -> 355 (box-free: width already 356, height 793)
    for y in range(1, 741):
        assert all(c == " " for c in G[y][318:356]), y
        G[y][317] = " "
        G[y][355] = "|"
    for x in range(318, 356):
        G[0][x] = "-"; G[741][x] = "-"
    G[0][355] = "+"; G[741][355] = "+"
    G[0][317] = "-"; G[741][317] = "-"
    put(G, 125, 2, ">", " ")   # second man walks east into the new strip
    put(G, 350, 2, "H", " ")   # ... and parks there
else:
    raise SystemExit("unknown variant")

out = f"solutions/little-little-man/fork-{variant}.man"
save(G, out)
print("wrote", out)
