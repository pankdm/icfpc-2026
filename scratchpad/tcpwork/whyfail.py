#!/usr/bin/env python3
"""For W=22, CH=14: report which pipe first fails to route, per placement.

Prints the geometry as rectangles + a free-cell census rather than a grid, so
the constraint is auditable without dumping ASCII art.

usage: whyfail.py [W] [CH] [RH]
"""
import sys
from collections import deque

W = int(sys.argv[1]) if len(sys.argv) > 1 else 22
CH = int(sys.argv[2]) if len(sys.argv) > 2 else 14
RH = int(sys.argv[3]) if len(sys.argv) > 3 else 13
RW, H = 18, RH + 2 + 7


def cells(r):
    x, y, w, h = r
    return {(x + i, y + j) for i in range(w) for j in range(h)}


def walls(r):
    x, y, w, h = r
    s = set()
    for i in range(w):
        s.add((x + i, y)); s.add((x + i, y + h - 1))
    for j in range(h):
        s.add((x, y + j)); s.add((x + w - 1, y + j))
    return s


def route(src, dst, blocked, filt, allw):
    sw, dw = walls(src), walls(dst)
    out = []
    for (bx, by) in sw:
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s = (bx + d[0], by + d[1])
            if not (0 <= s[0] < W and 0 <= s[1] < H) or s in blocked:
                continue
            if s in cells(src) or s in cells(dst):
                continue
            nxt = (s[0] + d[0], s[1] + d[1])
            if not (0 <= nxt[0] < W and 0 <= nxt[1] < H) or nxt in dw:
                continue
            if nxt in blocked or nxt in cells(src):
                continue
            seen, q = {s, nxt}, deque([(nxt, [s, nxt])])
            while q:
                cur, path = q.popleft()
                for e in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (cur[0] + e[0], cur[1] + e[1])
                    if not (0 <= n[0] < W and 0 <= n[1] < H):
                        continue
                    if n in dw and len(path) >= 2:
                        if filt is None or filt(n):
                            full, ok = path + [n], True
                            for i in range(1, len(full) - 1):
                                dd = (full[i + 1][0] - full[i][0], full[i + 1][1] - full[i][1])
                                if (full[i][0] - dd[0], full[i][1] - dd[1]) in allw:
                                    ok = False; break
                            if ok:
                                out.append(full)
                        continue
                    if n in seen or n in blocked or n in dw or len(path) > 30:
                        continue
                    seen.add(n)
                    q.append((n, path + [n]))
    return out


reader, sweeper = (0, 0, RW, RH), (0, RH + 2, RW, 7)
base = cells(reader) | cells(sweeper)
for c in range(1, 17):
    base |= {(c, RH), (c, RH + 1)}

print(f'grid {W}x{H}   reader cols 0-{RW-1} rows 0-{RH-1}   '
      f'lanes cols 1-16 rows {RH},{RH+1}   sweeper cols 0-{RW-1} rows {RH+2}-{H-1}')
free_out = sorted(p for p in [(x, y) for x in range(RW) for y in range(H)] if p not in base)
print(f'free cells left of the band: {free_out}')
print(f'band = cols {RW}-{W-1} x rows 0-{H-1} = {(W-RW)*H} cells; '
      f'checker {4*CH} + I 9 + O 9 = {4*CH+18} used, {(W-RW)*H-4*CH-18} left for 4 pipes\n')

for cy in range(0, H - CH + 1):
    checker = (RW, cy, 4, CH)
    north = {(RW + 1, cy), (RW + 2, cy)}
    south = {(RW + 1, cy + CH - 1), (RW + 2, cy + CH - 1)}
    bestgot, bestwhy = -1, ''
    for iy in range(0, H - 2):
        for ix in range(RW, W - 2):
            iroom = (ix, iy, 3, 3)
            if cells(iroom) & (cells(checker) | base):
                continue
            for oy in range(0, H - 2):
                for ox in range(RW, W - 2):
                    oroom = (ox, oy, 3, 3)
                    if cells(oroom) & (cells(checker) | cells(iroom) | base):
                        continue
                    blk = base | cells(checker) | cells(iroom) | cells(oroom)
                    allw = set()
                    for rm in (reader, sweeper, checker, iroom, oroom):
                        allw |= walls(rm)
                    # U tells pipes apart by END ARROWHEAD direction, so either
                    # assignment of {seq,drain} to {north,south} wall is legal --
                    # the checker's interior just mirrors vertically. Try both.
                    for sqw, drw in ((north, south), (south, north)):
                        plans = [('input', iroom, reader, None),
                                 ('seq', reader, checker, lambda n, w=sqw: n in w),
                                 ('drain', sweeper, checker, lambda n, w=drw: n in w),
                                 ('output', checker, oroom, None)]
                        got, blocked = 0, blk
                        for name, a, b, filt in plans:
                            ps = route(a, b, blocked, filt, allw)
                            if not ps:
                                break
                            blocked = blocked | set(ps[0][:-1])
                            got += 1
                        if got > bestgot:
                            bestgot = got
                            nm = ['input', 'seq', 'drain', 'output']
                            bestwhy = ('ALL 4 ROUTED' if got == 4 else f'first failure: {nm[got]}') + \
                                      f'   (I={iroom[:2]} O={oroom[:2]} seq={"N" if sqw is north else "S"})'
                    if False:
                        bestgot = got
                        nm = ['input', 'seq', 'drain', 'output']
                        bestwhy = ('ALL 4 ROUTED' if got == 4 else f'first failure: {nm[got]}') + \
                                  f'   (I={iroom[:2]} O={oroom[:2]})'
    lo, hi = cy, cy + CH - 1
    print(f'  checker rows {lo:2d}-{hi:2d}: routed {max(bestgot,0)}/4  {bestwhy}')
