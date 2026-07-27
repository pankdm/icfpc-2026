#!/usr/bin/env python3
"""Emit a 22x22 skeleton with every ROOM placed and the four pipes MISSING.

This is a viewing aid, not a runnable program: cells that a pipe could legally
occupy are marked '.' so the remaining freedom is visible at a glance. Draw the
four pipes over the dots and it becomes a real candidate.

Rooms use the best placement the router found (3 of 4 pipes route there):
  reader  cols 0-17  rows 0-12      lanes cols 1-16 rows 13-14
  sweeper cols 0-17  rows 15-21
  checker cols 18-21 rows 8-21      I room cols 18-20 rows 0-2
  O room  cols 19-21 rows 3-5

Pipes still to place:
  input : I room  -> reader   (any wall)
  seq   : reader  -> checker  (north wall row 8, interior col 19 or 20)
  drain : sweeper -> checker  (opposite wall from seq)
  output: checker -> O room

usage: mk22skeleton.py [out.man]
"""
import sys

sys.path.insert(0, '/Users/visenbaev/icfpc26/solutions/tcp')
W, H, RH = 22, 22, 13
READER = [
    "v     sN<      <", " > rb]]]Y  @r1M^", ">^  v]]bxb]]v   ",
    "  vbxbv   vbxbv ", "  ]   ]   ]   ] ", " vxv vxv vxv vxv",
    " & & & & & & & &", "vXvXvXvXvXvXvXvX", "rrrrrrrrrrrrrrrr",
    "ssssssssssssssss", "HHHHHHHHHHHHHHHH",
]
SWEEPER = ["v<v<v<v<v<v<v<v<", "rsrsrsrsrsrsrsrs",
           "srsrsrsrsrsrsrsr", "v^<^<^<^<^<^<^<^", ">@             ^"]
CHK_L, CHK_R = ">1sU+ba1NsH@", "v+M<  ^M*M4^"

g = [[' '] * W for _ in range(H)]


def room(x, y, w, h):
    for i in range(w):
        g[y][x + i] = '-'; g[y + h - 1][x + i] = '-'
    for j in range(h):
        g[y + j][x] = '|'; g[y + j][x + w - 1] = '|'
    for a, b in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
        g[b][a] = '+'


for j, line in enumerate(READER):
    for i, ch in enumerate(line):
        if ch != ' ':
            g[1 + j][1 + i] = ch
room(0, 0, 18, RH)
for c in range(1, 17):
    g[RH][c] = 'v'; g[RH + 1][c] = 'v'
for j, line in enumerate(SWEEPER):
    for i, ch in enumerate(line):
        if ch != ' ':
            g[RH + 3 + j][1 + i] = ch
room(0, RH + 2, 18, 7)

CX, CY = 18, 8
for j, ch in enumerate(CHK_L):
    if ch != ' ':
        g[CY + 1 + j][CX + 1] = ch
for j, ch in enumerate(CHK_R):
    if ch != ' ':
        g[CY + 1 + j][CX + 2] = ch
room(CX, CY, 4, 14)
room(18, 0, 3, 3); g[1][19] = 'I'
room(19, 3, 3, 3); g[4][20] = 'O'

free = [(x, y) for y in range(H) for x in range(W) if g[y][x] == ' ']
for x, y in free:
    g[y][x] = '.'

out = sys.argv[1] if len(sys.argv) > 1 else \
    '/Users/visenbaev/icfpc26/scratchpad/tcpwork/skeleton-22x22.man'
open(out, 'w').write('\n'.join(''.join(r) for r in g) + '\n')
print(f'wrote {out}   22x22, {len(free)} free cells marked "."')
bycol = {}
for x, y in free:
    bycol.setdefault(x, []).append(y)
for x in sorted(bycol):
    print(f'  col {x:2d}: rows {sorted(bycol[x])}')
