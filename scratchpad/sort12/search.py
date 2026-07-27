#!/usr/bin/env python3
"""Exhaustive floorplan + pipe-routing search for sort-numbers in a 12x12 box.

Rooms: main (interior 8x6, mainroom.BASE), relay (interior 3x2), input 3x3,
output 3x3.  Enumerates every non-overlapping placement, every assignment of the
four pipe attachment cells on the main room, filters on the nearest-pipe /
reading-order constraints, then routes the pipes (return pipe >= RET_MIN cells).

usage: python3 search.py [--out DIR] [--max N] [--verbose]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainroom

BOX = int(os.environ.get("SORTBOX", "12"))
ARROW = {(1, 0): '>', (-1, 0): '<', (0, 1): 'v', (0, -1): '^'}
STEPS = list(ARROW)
RET_MIN = 15          # return pipe alone must hold n-1 = 15 values


def rect_cells(r):
    x0, y0, x1, y1 = r
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def border_cells(r):
    x0, y0, x1, y1 = r
    s = set()
    for x in range(x0, x1 + 1):
        s.add((x, y0)); s.add((x, y1))
    for y in range(y0, y1 + 1):
        s.add((x0, y)); s.add((x1, y))
    return s


def inside(p):
    return 0 <= p[0] < BOX and 0 <= p[1] < BOX


def nearer(cands, pos):
    """cands: list of (key, cell).  Return the key the engine would pick."""
    return min(cands, key=lambda kc: (abs(kc[1][0] - pos[0]) + abs(kc[1][1] - pos[1]),
                                      kc[1][1], kc[1][0]))[0]


class Plan:
    def __init__(self, rooms):
        self.rooms = rooms                     # name -> rect
        self.occ = set()
        for r in rooms.values():
            self.occ |= rect_cells(r)
        self.free = {(x, y) for x in range(BOX) for y in range(BOX)} - self.occ
        self.bord = {k: border_cells(r) for k, r in rooms.items()}
        self.bmap = {}
        for k, b in self.bord.items():
            for c in b:
                self.bmap[c] = k

    def srcs(self, room):
        """free cells that can START a pipe leaving `room`, as (cell, dir)"""
        out = []
        for c in self.free:
            for d in STEPS:
                if self.bmap.get((c[0] - d[0], c[1] - d[1])) == room:
                    out.append((c, d))
        return out

    def dsts(self, room):
        """free cells that can END a pipe entering `room`, as (cell, dir)"""
        out = []
        for c in self.free:
            for d in STEPS:
                if self.bmap.get((c[0] + d[0], c[1] + d[1])) == room:
                    out.append((c, d))
        return out


def route(plan, start, sdir, end, edir, blocked, lo, hi, want=1, budget=200000):
    """simple paths start->end through free cells; dirs[i] leaves cells[i].
    Path must not pass adjacent-into any room border before `end`, and no cell
    other than `start` may have a room border behind it (spurious pipe start)."""
    free = plan.free - blocked
    res = []
    st = [(start, sdir, [start], [sdir], {start})]
    n = 0
    while st and len(res) < want:
        n += 1
        if n > budget:
            break
        c, d, cells, ds, seen = st.pop()
        nxt = (c[0] + d[0], c[1] + d[1])
        if c == end and d == edir:
            if lo <= len(cells) <= hi:
                res.append((list(cells), list(ds)))
            continue
        if not inside(nxt) or nxt in plan.bmap or nxt not in free or nxt in seen:
            continue
        if len(cells) >= hi:
            continue
        for nd in STEPS:
            back = (nxt[0] - nd[0], nxt[1] - nd[1])
            if back in plan.bmap:
                continue                     # would be a second pipe start
            st.append((nxt, nd, cells + [nxt], ds + [nd], seen | {nxt}))
    return res


def route_long(plan, start, sdir, end, edir, blocked, lo, hi, budget=400000):
    """longest-first: same as route() but returns the longest path found."""
    free = plan.free - blocked
    best = None
    st = [(start, sdir, [start], [sdir], {start})]
    n = 0
    while st:
        n += 1
        if n > budget:
            break
        c, d, cells, ds, seen = st.pop()
        nxt = (c[0] + d[0], c[1] + d[1])
        if c == end and d == edir:
            if lo <= len(cells) <= hi and (best is None or len(cells) > len(best[0])):
                best = (list(cells), list(ds))
            continue
        if not inside(nxt) or nxt in plan.bmap or nxt not in free or nxt in seen:
            continue
        if len(cells) >= hi:
            continue
        for nd in STEPS:
            back = (nxt[0] - nd[0], nxt[1] - nd[1])
            if back in plan.bmap:
                continue
            st.append((nxt, nd, cells + [nxt], ds + [nd], seen | {nxt}))
    return best


def render(plan, mgrid, relay_flow, pipes):
    g = [[' '] * BOX for _ in range(BOX)]

    def put(x, y, ch):
        if g[y][x] != ' ':
            raise ValueError("collision (%d,%d)" % (x, y))
        g[y][x] = ch

    for name, r in plan.rooms.items():
        x0, y0, x1, y1 = r
        for x in range(x0, x1 + 1):
            put(x, y0, '-' if x0 < x < x1 else '+')
            put(x, y1, '-' if x0 < x < x1 else '+')
        for y in range(y0 + 1, y1):
            put(x0, y, '|'); put(x1, y, '|')
    mx, my = plan.rooms['main'][0], plan.rooms['main'][1]
    for j, line in enumerate(mgrid):
        for i, ch in enumerate(line):
            if ch != ' ':
                put(mx + 1 + i, my + 1 + j, ch)
    rx, ry, rx1, ry1 = plan.rooms['relay']
    cells = mainroom.relay_cells(rx1 - rx - 1, ry1 - ry - 1, relay_flow)
    if not cells:
        return None
    for (x, y), ch in cells[0].items():
        put(rx + 1 + x, ry + 1 + y, ch)
    ix, iy, ix1, iy1 = plan.rooms['inp']
    put((ix + ix1) // 2, (iy + iy1) // 2, 'I')
    ox, oy, ox1, oy1 = plan.rooms['outp']
    put((ox + ox1) // 2, (oy + oy1) // 2, 'O')
    for cells_, ds in pipes:
        for c, d in zip(cells_, ds):
            put(c[0], c[1], ARROW[d])
    return "\n".join("".join(r).rstrip() for r in g) + "\n"
