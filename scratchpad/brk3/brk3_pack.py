#!/usr/bin/env python3
"""Can brackets' five rooms be packed into 16x16 with all four pipes routable?

Each room may take any rectangle whose interior can still hold its cells, and may
be transposed (transposing a room is a true pure fold: swap x/y and remap
> <-> v, < <-> ^, and the walk, op order and tick count are unchanged).

Reports, for every packing found, the interior fill each room would need -- i.e.
exactly how much densification 16x16 costs.  Prints only the best few.
"""
import sys
from itertools import product

BOX = int(sys.argv[1]) if len(sys.argv) > 1 else 16
NEED = {"M": 56, "P": 20, "C": 28}          # interior cells each room must hold
MAXFILL = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
PIPES = [("I", "C"), ("C", "M"), ("M", "P"), ("P", "O")]


def rects(need, maxfill):
    """Room rectangles that can hold `need` interior cells at <= maxfill."""
    out = []
    for w in range(3, BOX + 1):
        for h in range(3, BOX + 1):
            inter = (w - 2) * (h - 2)
            if inter <= 0 or need > inter * maxfill:
                continue
            if min(w - 2, h - 2) < 3:        # a 1- or 2-cell-wide interior
                continue                     # cannot carry a branching loop
            out.append((w, h, need / inter))
    out.sort(key=lambda t: w * h if False else t[0] * t[1])
    return out


CAND = {n: rects(NEED[n], MAXFILL) for n in NEED}
CAND["I"] = [(3, 3, 1.0)]
CAND["O"] = [(3, 3, 1.0)]
ORDER = ["M", "P", "C", "I", "O"]


def border(x, y, w, h):
    return {(x + i, y + j) for i in range(w) for j in range(h)
            if i in (0, w - 1) or j in (0, h - 1)}


def solve():
    best = []
    placed = {}
    occ = [[None] * BOX for _ in range(BOX)]

    def fits(x, y, w, h):
        if x < 0 or y < 0 or x + w > BOX or y + h > BOX:
            return False
        for j in range(y, y + h):
            row = occ[j]
            for i in range(x, x + w):
                if row[i] is not None:
                    return False
        return True

    def mark(x, y, w, h, v):
        for j in range(y, y + h):
            for i in range(x, x + w):
                occ[j][i] = v

    def pipes_ok():
        free = {(i, j) for j in range(BOX) for i in range(BOX) if occ[j][i] is None}
        for src, dst in PIPES:
            sx, sy, sw, sh = placed[src]
            dx, dy, dw, dh = placed[dst]
            sb, db = border(sx, sy, sw, sh), border(dx, dy, dw, dh)
            starts = {c for c in free
                      if any((c[0] + a, c[1] + b) in sb
                             for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
            ends = {c for c in free
                    if any((c[0] + a, c[1] + b) in db
                           for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
            # BFS for a >=2-cell free path from a start cell to an end cell
            seen, frontier, depth, hit = set(starts), set(starts), 1, False
            while frontier and depth < 40:
                if depth >= 2 and (frontier & ends):
                    hit = True
                    break
                nxt = set()
                for (i, j) in frontier:
                    for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        c = (i + a, j + b)
                        if c in free and c not in seen:
                            seen.add(c)
                            nxt.add(c)
                frontier, depth = nxt, depth + 1
            if not hit:
                return False
        return True

    def rec(k):
        if len(best) >= 4000:
            return
        if k == len(ORDER):
            if pipes_ok():
                fill = {n: placed[n] for n in ORDER}
                worst = max(NEED[n] / ((fill[n][2] - 2) * (fill[n][3] - 2))
                            for n in NEED)
                best.append((round(worst, 3),
                             {n: (fill[n][2], fill[n][3]) for n in NEED}))
            return
        name = ORDER[k]
        for (w, h, _) in CAND[name]:
            for x in range(BOX - w + 1):
                for y in range(BOX - h + 1):
                    if not fits(x, y, w, h):
                        continue
                    placed[name] = (x, y, w, h)
                    mark(x, y, w, h, name)
                    rec(k + 1)
                    mark(x, y, w, h, None)
            placed.pop(name, None)

    rec(0)
    return best


res = solve()
print("box %d: %d packings found" % (BOX, len(res)))
if res:
    res.sort()
    seen = set()
    for worst, shape in res:
        key = tuple(sorted(shape.items()))
        if key in seen:
            continue
        seen.add(key)
        print("  worst required fill %.0f%%   %s" % (
            100 * worst, "  ".join("%s %dx%d" % (n, w, h)
                                   for n, (w, h) in sorted(shape.items()))))
        if len(seen) >= 5:
            break
