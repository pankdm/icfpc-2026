#!/usr/bin/env python3
"""22x22 with the I/O + checker band on the LEFT instead of the right.

Why this is not merely a mirror image: `Y`'s CW copy keeps the splitter's runner
slot and so wins pipe contention, which forces the demux clone to be the CW
copy, which forces the parent to enter `Y` heading EAST, which forces the loop's
return leg to run WEST. So the reader's seq `s` always ends up on the reader's
WEST side. Putting the band on the west therefore puts the seq pipe's source
NEAR that `s` instead of 11 columns away, which is the constraint that killed
every band-on-the-right packing.

  reader  cols 4-21 rows 0-12      lanes cols 5-20 rows 13-14
  sweeper cols 4-21 rows 15-21     band  cols 0-3, all 22 rows
  leaves at cols 5-20, so L1/`Y` sit at col 13 and the return leg's `N`,`s`
  land at cols 12,11 -> `s` at (11,1), its own lane attach at (11,13).

usage: mirror22.py [CH] [SX] [SY]
"""
import sys
from collections import deque

CH = int(sys.argv[1]) if len(sys.argv) > 1 else 14
SX = int(sys.argv[2]) if len(sys.argv) > 2 else 11
SY = int(sys.argv[3]) if len(sys.argv) > 3 else 1
W, H, RH = 22, 22, 13
RX = 4


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
                                dd = (full[i + 1][0] - full[i][0],
                                      full[i + 1][1] - full[i][1])
                                if (full[i][0] - dd[0], full[i][1] - dd[1]) in allw:
                                    ok = False
                                    break
                            if ok:
                                out.append(full)
                        continue
                    if n in seen or n in blocked or n in dw or len(path) > 30:
                        continue
                    seen.add(n)
                    q.append((n, path + [n]))
    return out


reader, sweeper = (RX, 0, 18, RH), (RX, RH + 2, 18, 7)
base = cells(reader) | cells(sweeper)
for c in range(RX + 1, RX + 17):
    base |= {(c, RH), (c, RH + 1)}
LANE = RH - SY

SOLS = []
print(f'reader cols {RX}-{RX+17}; band cols 0-{RX-1}; seq `s` ({SX},{SY}); '
      f'its lane is {LANE} away')
for cy in range(0, H - CH + 1):
    checker = (0, cy, 4, CH)
    if cells(checker) & base:
        continue
    W4 = {'N': {(1, cy), (2, cy)}, 'S': {(1, cy + CH - 1), (2, cy + CH - 1)},
          'W': {(0, y) for y in range(cy + 1, cy + CH - 1)},
          'E': {(3, y) for y in range(cy + 1, cy + CH - 1)}}
    got_best, why = 0, ''
    for iy in range(0, H - 2):
        for ix in range(0, RX - 2):
            iroom = (ix, iy, 3, 3)
            if cells(iroom) & (cells(checker) | base):
                continue
            for oy in range(0, H - 2):
                for ox in range(0, RX - 2):
                    oroom = (ox, oy, 3, 3)
                    if cells(oroom) & (cells(checker) | cells(iroom) | base):
                        continue
                    blk = base | cells(checker) | cells(iroom) | cells(oroom)
                    allw = set()
                    for rm in (reader, sweeper, checker, iroom, oroom):
                        allw |= walls(rm)
                    for sn, sqw in W4.items():
                        for dn, drw in W4.items():
                            if sn == dn:
                                continue
                            plans = [('input', iroom, reader, None),
                                     ('seq', reader, checker, lambda n, w=sqw: n in w),
                                     ('drain', sweeper, checker, lambda n, w=drw: n in w),
                                     ('output', checker, oroom, None)]
                            got, blocked, keep = 0, blk, {}
                            for nm, a, b, filt in plans:
                                ps = route(a, b, blocked, filt, allw)
                                if nm == 'seq':
                                    def wins(q):
                                        d = abs(q[0][0] - SX) + abs(q[0][1] - SY)
                                        return d < LANE or (d == LANE and
                                                            (q[0][1], q[0][0]) < (RH, SX))
                                    ps = [q for q in ps if wins(q)]
                                if not ps:
                                    break
                                ps.sort(key=len)
                                keep[nm] = ps[0]
                                blocked = blocked | set(ps[0][:-1])
                                got += 1
                            if got == 4:
                                SOLS.append((cy, iroom[:2], oroom[:2], sn, dn, dict(keep)))
                            if got > got_best:
                                got_best = got
                                why = f'I={iroom[:2]} O={oroom[:2]} seq={sn} drain={dn}'
    tag = 'ALL 4 ROUTED' if got_best == 4 else f'{got_best}/4 best'
    print(f'  checker rows {cy:2d}-{cy+CH-1:2d}: {tag}  {why}')

print()
combos = {}
for cy, ir, orm, sn, dn, k in SOLS:
    combos.setdefault((sn, dn), []).append((cy, ir, orm, k))
print('wall combos that achieve 4/4:')
for (sn, dn), v in sorted(combos.items()):
    cy, ir, orm, k = v[0]
    print(f'  seq={sn} drain={dn}: {len(v)} solutions; e.g. checker rows {cy}-{cy+CH-1} '
          f'I={ir} O={orm}')
    for nm in ('input', 'seq', 'drain', 'output'):
        print(f'      {nm:7s} {k[nm][:-1]} -> {k[nm][-1]}')
