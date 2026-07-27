#!/usr/bin/env python3
"""Trace every pipe in a .man exactly the way interp/src/lib.rs does, so a
re-route can preserve each pipe's cell COUNT (capacity/delay) while changing its
path.  Prints one line per pipe: index, endpoints, length, column span.

    python3 scratchpad/ss2/pipes.py [file.man] [--cells N]   # dump pipe N's cells
"""
import sys

MAN = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/ss2/teammate.man"
g = [l.rstrip("\n") for l in open(MAN).read().split("\n")]
while g and not g[-1].strip():
    g.pop()
W = max(len(l) for l in g)
H = len(g)


def at(x, y):
    if 0 <= y < H and 0 <= x < len(g[y]):
        return g[y][x]
    return " "


ARR = {">": (1, 0), "<": (-1, 0), "v": (0, 1), "^": (0, -1), "V": (0, 1)}

rooms = []
claimed = set()
for y0 in range(H):
    for x0 in range(W):
        if at(x0, y0) != "+":
            continue
        for hc, vc in (("-", "|"), ("=", ":")):
            x1 = x0 + 1
            while at(x1, y0) == hc:
                x1 += 1
            if x1 <= x0 + 1 or at(x1, y0) != "+":
                continue
            y1 = y0 + 1
            while at(x0, y1) == vc:
                y1 += 1
            if y1 <= y0 + 1 or at(x0, y1) != "+":
                continue
            if at(x1, y1) != "+":
                continue
            if not (all(at(x, y1) == hc for x in range(x0 + 1, x1))
                    and all(at(x1, y) == vc for y in range(y0 + 1, y1))):
                continue
            per = {(x, y0) for x in range(x0, x1 + 1)} | {(x, y1) for x in range(x0, x1 + 1)} \
                | {(x0, y) for y in range(y0, y1 + 1)} | {(x1, y) for y in range(y0, y1 + 1)}
            if per & claimed:
                continue
            claimed |= per
            rooms.append((x0, y0, x1, y1))
            break

interior = set()
border = {}
for i, (x0, y0, x1, y1) in enumerate(rooms):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            if x in (x0, x1) or y in (y0, y1):
                border[(x, y)] = i
            else:
                interior.add((x, y))


def is_pipe_glyph(p):
    c = at(p[0], p[1])
    return (c in ARR or c in "-|") and p not in border and p not in interior


pipes = []
used = set()
for y in range(H):
    for x in range(W):
        c = at(x, y)
        if c not in ARR or not is_pipe_glyph((x, y)) or (x, y) in used:
            continue
        d = ARR[c]
        if (x - d[0], y - d[1]) not in border:
            continue
        path = [(x, y)]
        pos, dr = (x, y), d
        ok = True
        while True:
            nxt = (pos[0] + dr[0], pos[1] + dr[1])
            if nxt in border:
                break
            if not is_pipe_glyph(nxt) or len(path) > W * H:
                ok = False
                break
            path.append(nxt)
            pos = nxt
            if at(nxt[0], nxt[1]) in ARR:
                dr = ARR[at(nxt[0], nxt[1])]
        if not ok:
            continue
        used |= set(path)
        pipes.append((path, border[(x - d[0], y - d[1])], border[nxt]))

print("rooms %d  pipes %d" % (len(rooms), len(pipes)))
for i, (r) in enumerate(rooms):
    print("  room %2d %s" % (i, r))
for i, (path, src, dst) in enumerate(pipes):
    xs = [p[0] for p in path]
    ys = [p[1] for p in path]
    tag = " <== USES COLS>=85" if max(xs) >= 85 else ""
    print("  pipe %2d  r%d->r%d  len=%3d  x %d..%d  y %d..%d  head=%s tail=%s%s"
          % (i, src, dst, len(path), min(xs), max(xs), min(ys), max(ys),
             path[0], path[-1], tag))
if "--cells" in sys.argv:
    n = int(sys.argv[sys.argv.index("--cells") + 1])
    print("pipe %d cells:" % n, pipes[n][0])
