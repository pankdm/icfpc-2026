#!/usr/bin/env python3
"""Print the full 22x22 solution (rooms + the four pipe paths) for one placement.

usage: show22.py [cy]
"""
import sys
from collections import deque

sys.path.insert(0, '/Users/visenbaev/icfpc26/scratchpad/tcpwork')
CY = int(sys.argv[1]) if len(sys.argv) > 1 else 7
# whyfail parses sys.argv at import time -- hand it the real geometry, not ours
sys.argv = ['whyfail', '22', '14', '13']
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import whyfail as WF

W, H, RW, RH = 22, 22, 18, 13
CH = 14

cells, walls, route = WF.cells, WF.walls, WF.route
reader, sweeper = (0, 0, RW, RH), (0, RH + 2, RW, 7)
base = cells(reader) | cells(sweeper)
for c in range(1, 17):
    base |= {(c, RH), (c, RH + 1)}

checker = (RW, CY, 4, CH)
north = {(RW + 1, CY), (RW + 2, CY)}
south = {(RW + 1, CY + CH - 1), (RW + 2, CY + CH - 1)}
west = {(RW, y) for y in range(CY + 1, CY + CH - 1)}
east = {(RW + 3, y) for y in range(CY + 1, CY + CH - 1)}
W4 = {'N': north, 'S': south, 'W': west, 'E': east}

found = None
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
                for sn, sqw in W4.items():
                    for dn, drw in W4.items():
                        if sn == dn:
                            continue
                        plans = [('input', iroom, reader, None),
                                 ('seq', reader, checker, lambda n, w=sqw: n in w),
                                 ('drain', sweeper, checker, lambda n, w=drw: n in w),
                                 ('output', checker, oroom, None)]
                        blocked, got, paths = blk, 0, {}
                        for nm, a, b, filt in plans:
                            ps = route(a, b, blocked, filt, allw)
                            if not ps:
                                break
                            ps.sort(key=len)
                            paths[nm] = ps[0]
                            blocked = blocked | set(ps[0][:-1])
                            got += 1
                        if got == 4 and found is None:
                            found = (iroom, oroom, sn, dn, paths)
if not found:
    print(f'cy={CY}: no full solution'); sys.exit()
iroom, oroom, sn, dn, paths = found
print(f'checker cols {RW}-{RW+3} rows {CY}-{CY+CH-1}   seq wall={sn}  drain wall={dn}')
print(f'I room cols {iroom[0]}-{iroom[0]+2} rows {iroom[1]}-{iroom[1]+2}')
print(f'O room cols {oroom[0]}-{oroom[0]+2} rows {oroom[1]}-{oroom[1]+2}')
for nm in ('input', 'seq', 'drain', 'output'):
    p = paths[nm]
    print(f'  {nm:7s} cells {p[:-1]}  -> attaches at {p[-1]}')
