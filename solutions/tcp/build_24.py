#!/usr/bin/env python3
"""tcp 22x22 (box 484) -- the band moved to the LEFT of the reader.

Every band-on-the-right packing dies on pipe BINDING, not geometry. `Y`'s CW
copy keeps the splitter's runner slot and therefore wins pipe contention, so the
demux clone must be the CW copy, so the parent must enter `Y` heading EAST, so
the loop's return leg must run WEST -- which puts the reader's seq `s` on the
reader's WEST side. With the band on the east that `s` is ~11 columns from the
seq pipe's source but only 12 from its own lane pipe directly below, and the
lane wins. Moving the band to the WEST puts the source next to the `s` instead.

Layout (searched exhaustively by scratchpad/tcpwork/mirror22.py, which enforces
routing AND the binding rule):

  band    cols 0-3, all rows      reader cols 4-21 rows 0-12
  checker cols 0-3 rows 8-20      lanes  cols 5-20 rows 13-14
  I room  cols 1-3 rows 0-2       sweeper cols 4-21 rows 15-21
  O room  cols 0-2 rows 3-5

  input  (3,3)(3,4)(3,5)(3,6) -> (4,6)   reader west wall
  seq    (3,7)(2,7)           -> (2,8)   checker north wall
  drain  (3,21)(2,21)         -> (2,20)  checker south wall
  output (0,7)(0,6)           -> (0,5)   O room

seq/drain keep the north/south assignment, so the checker interior transplants
unchanged from the 13-row K=8 variant. The reader is byte-identical to the
earlier 22x22 attempt, shifted right by 4: leaves now sit at cols 5-20, so L1
and `Y` are at col 13 and the return leg's `W 8 - s 1 M` land at cols 12..7,
putting `s` at (9,1). Its lane attach is (9,13), distance 12; the seq source
(3,7) is also 12 away and wins the (dist,row,col) tiebreak because row 7
precedes row 13.

usage: build_24.py [out.man]
"""
import sys

W, H = 22, 22
RX, RH = 4, 13                       # reader/sweeper left edge, reader height
CX, CY, CH = 0, 8, 13                # checker

READER = [
    "v M1s-8W<      <",              # 1  return leg runs WEST: W 8 - s then 1 M
    " > rb]]]Y  @r1M^",              # 2  main loop runs EAST into the fork
    ">^  v]]bxb]]v   ",              # 3  level 1; cols 5-6 are the loop's dip
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
CHK_L = ">1sU+ba1Ns@"                # 11 interior rows, no `H`
CHK_R = "v+M<  ^ M8^"                # init is `8 M`: K=8, so the reader sends 8-seq


def main(out='/tmp/tcp24.man'):
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
            put(RX + 1 + i, 1 + j, ch)
    room(RX, 0, 18, RH)
    for c in range(RX + 1, RX + 17):
        put(c, RH, 'v'); put(c, RH + 1, 'v')
    for j, line in enumerate(SWEEPER):
        for i, ch in enumerate(line):
            put(RX + 1 + i, RH + 3 + j, ch)
    room(RX, RH + 2, 18, 7)

    for j, ch in enumerate(CHK_L):
        put(CX + 1, CY + 1 + j, ch)
    for j, ch in enumerate(CHK_R):
        put(CX + 2, CY + 1 + j, ch)
    room(CX, CY, 4, CH)

    room(1, 0, 3, 3); put(2, 1, 'I')             # I room cols 1-3 rows 0-2
    room(0, 3, 3, 3); put(1, 4, 'O')             # O room cols 0-2 rows 3-5
    for y in (3, 4, 5):                          # input -> reader west wall (4,6)
        put(3, y, 'v')
    put(3, 6, '>')
    put(3, 7, '<'); put(2, 7, 'v')               # seq -> checker north wall (2,8)
    put(3, 21, '<'); put(2, 21, '^')             # drain -> checker south wall (2,20)
    put(0, 7, '^'); put(0, 6, '^')               # output -> O room (0,5)

    txt = '\n'.join(''.join(r).rstrip() for r in g).rstrip('\n') + '\n'
    open(out, 'w').write(txt)
    ls = txt.rstrip('\n').split('\n')
    ww = max(len(r) for r in ls)
    xs = [x for x in range(ww) if any(len(r) > x and r[x] != ' ' for r in ls)]
    ys = [i for i, r in enumerate(ls) if r.strip()]
    bw, bh = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    print(f'wrote {out}  {bw}x{bh}  box {max(bw, bh) ** 2}')


main(*sys.argv[1:2])
