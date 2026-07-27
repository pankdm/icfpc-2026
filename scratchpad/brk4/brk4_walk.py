#!/usr/bin/env python3
"""Statically enumerate a room's walk graph: states (pos,dir) -> successors.

Gives the exact op sequence and every branch's outcome cells, which is what a
re-lay needs.  Turn glyphs set direction; d/a/x/X are turn-AND-test so they have
2-3 successors; everything else continues straight.

  python3 scratchpad/brk4/brk4_walk.py <man> <x0> <y0> <x1> <y1> <sx> <sy>
"""
import sys

man = sys.argv[1]
x0, y0, x1, y1, sx, sy = map(int, sys.argv[2:8])
rows = open(man).read().split("\n")
while rows and not rows[-1].strip():
    rows.pop()
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]

E, W, S, N = (1, 0), (-1, 0), (0, 1), (0, -1)
CW = {E: S, S: W, W: N, N: E}
CCW = {v: k for k, v in CW.items()}
TURN = {">": E, "<": W, "^": N, "v": S, "V": S}


def succ(x, y, d):
    ch = rows[y][x]
    if ch in TURN:
        return [(TURN[ch], "turn")]
    if ch == "X":
        return [(CW[d], "A>0"), (CCW[d], "A<0"), (d, "A==0")]
    if ch == "d":
        return [(CW[d], "BP>0"), (d, "BP<=0")]
    if ch == "a":
        return [(CCW[d], "BP>0"), (d, "BP<=0")]
    if ch == "x":
        return [(CW[d], "bit1"), (CCW[d], "bit0")]
    if ch == "H":
        return []
    return [(d, "")]


seen = set()
stack = [((sx, sy), E)]
order = []
while stack:
    (x, y), d = stack.pop()
    if ((x, y), d) in seen:
        continue
    seen.add(((x, y), d))
    order.append(((x, y), d, rows[y][x]))
    for nd, lab in succ(x, y, d):
        nx, ny = x + nd[0], y + nd[1]
        if not (x0 < nx < x1 and y0 < ny < y1):
            order.append((("WALL", nx, ny), nd, lab))
            continue
        stack.append(((nx, ny), nd))

cells = sorted({p for p, _, _ in order if isinstance(p, tuple) and len(p) == 2})
print("states %d over %d cells" % (len(seen), len(cells)))
glyphs = {}
for p, d, ch in order:
    if isinstance(p, tuple) and len(p) == 2:
        glyphs[p] = ch
print("ops (non-turn, non-blank):")
ops = [(p, g) for p, g in sorted(glyphs.items()) if g not in " <>^vV"]
print("  count %d: %s" % (len(ops), "".join(g for _, g in ops)))
print("branches:")
for p, g in sorted(glyphs.items()):
    if g in "daxX":
        print("   %s at %s" % (g, p))
print("wall hits:", [(p, lab) for p, d, lab in order if len(p) == 3][:6])
