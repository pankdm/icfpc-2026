#!/usr/bin/env python3
"""tcp 23x22 (box 529) -- champion box, ~21% fewer ticks.

The 22x22 attempt died on a chain that was entirely a consequence of squeezing
to 22 columns: a 22-wide band cannot place a 14-row checker, which capped the
checker's init at 3 cells (max B=9, brute-forced), which capped K at 9, which
forced the reader to spend 3 ops making up c=16-K, which pushed the seq send to
col 5 where the lane pipe beneath it wins the binding contest.

Give the column back and every link falls at once:

  width 23 -> the 14-row checker places (bandsearch)
           -> 4 init cells -> B=16 via `4 M * M` -> K=16
           -> the reader only has to negate, one op (`N`)
           -> the seq send lands at col 7, and it wins the binding.

Box is unchanged, because max(23,22)^2 == max(23,23)^2 == 529. The gain is the
13-row reader: reader 13 + lanes 2 + sweeper 7 = 22 rows, and the shorter grid
shortens the main loop from the champion's 24-tick period to 19.

Reader loop (rows 1-2), fork `Y` at (9,2) with the man heading EAST so the CW
copy -- the one that keeps the splitter's runner slot, and so wins pipe
contention -- is the demux clone:

    row 2 eastward:  `>`(2) . `r`(4) `b`(5) `]`(6) `]`(7) `]`(8) `Y`(9)
    row 1 westward:  `<`(9) `N`(8) `s`(7) . . . . . `v`(1)

The demux clone needs 13 ticks from the fork to its leaf `r`; the loop man would
reach his own `r` in 12, so he would eat the packet value. Rows 3-4 have unused
WESTERN columns (the tree only starts at col 3-5 there), so the loop dips
(1,2)->(1,3)->(2,3)->(2,2) on its way back, costing 2 ticks and putting his read
at T+14 against the clone's T+13.

usage: build_23.py [out.man]
"""
import sys

W, H = 23, 22
CX, CY = 18, 3                       # checker: cols 18..21, rows 3..16
RH = 13                              # reader rows 0..12

READER = [
    "v     sN<      <",              # 1  return leg runs WEST; `N` then send -seq
    " > rb]]]Y@r1M  ^",              # 2  main loop runs EAST into the fork at col 9
    ">^  v]]bxb]]v   ",              # 3  level 1; cols 1-2 are the loop's dip
    "  vbxbv   vbxbv ",              # 4  level 2
    "  ]   ]   ]   ] ",              # 5  reload shift
    " vxv vxv vxv vxv",              # 6  level 3
    " & & & & & & & &",              # 7  isolate bit 0
    "vXvXvXvXvXvXvXvX",              # 8  level 4
    "rrrrrrrrrrrrrrrr",              # 9  read the packet value
    "ssssssssssssssss",              # 10 write it into the lane pipe
    "HHHHHHHHHHHHHHHH",              # 11 retire the demux man
]
SWEEPER = [
    "v<v<v<v<v<v<v<v<",
    "rsrsrsrsrsrsrsrs",
    "srsrsrsrsrsrsrsr",
    "v^<^<^<^<^<^<^<^",
    ">@             ^",
]
# 14-row checker, K=16: init `4 M * M` climbing column R, `H` retained.
CHK_L = ">1sU+ba1NsH@"
CHK_R = "v+M<  ^M*M4^"


def main(out='/tmp/tcp23.man'):
    g = [[' '] * W for _ in range(H)]

    def put(x, y, ch):
        if ch == ' ':
            return
        if g[y][x] not in (' ', ch):
            raise SystemExit(f'collision at ({x},{y}): {g[y][x]!r} vs {ch!r}')
        g[y][x] = ch

    def room(x, y, w, h):
        for i in range(w):
            g[y][x + i] = '-'; g[y + h - 1][x + i] = '-'
        for j in range(h):
            g[y + j][x] = '|'; g[y + j][x + w - 1] = '|'
        for a, b in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
            g[b][a] = '+'

    for j, line in enumerate(READER):
        for i, ch in enumerate(line):
            put(1 + i, 1 + j, ch)
    room(0, 0, 18, RH)
    for c in range(1, 17):                       # 16 lane pipes, 2 cells each
        put(c, RH, 'v'); put(c, RH + 1, 'v')
    for j, line in enumerate(SWEEPER):
        for i, ch in enumerate(line):
            put(1 + i, RH + 3 + j, ch)
    room(0, RH + 2, 18, 7)

    for j, ch in enumerate(CHK_L):
        put(CX + 1, CY + 1 + j, ch)
    for j, ch in enumerate(CHK_R):
        put(CX + 2, CY + 1 + j, ch)
    room(CX, CY, 4, 14)

    room(20, 0, 3, 3); put(21, 1, 'I')           # I room, cols 20..22 rows 0..2
    room(18, 19, 3, 3); put(19, 20, 'O')         # O room, cols 18..20 rows 19..21
    put(19, 1, '<'); put(18, 1, '<')             # input -> reader east wall
    put(18, 2, '>'); put(19, 2, 'v')             # seq   -> checker north wall
    put(18, 17, '>'); put(19, 17, '^')           # drain -> checker south wall
    put(21, 17, 'v'); put(21, 18, '<'); put(20, 18, 'v')   # output -> O room

    txt = '\n'.join(''.join(r).rstrip() for r in g).rstrip('\n') + '\n'
    open(out, 'w').write(txt)
    ls = txt.rstrip('\n').split('\n')
    ww = max(len(r) for r in ls)
    xs = [x for x in range(ww) if any(len(r) > x and r[x] != ' ' for r in ls)]
    ys = [i for i, r in enumerate(ls) if r.strip()]
    bw, bh = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    print(f'wrote {out}  {bw}x{bh}  box {max(bw, bh) ** 2}')


main(*sys.argv[1:2])
