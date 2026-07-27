#!/usr/bin/env python3
"""tcp 22x22 (box 484).

Height was 23 = reader(14) + lanes(2) + sweeper(7). Lanes are 2 (a pipe needs
2 cells) and the sweeper is 5 interior rows (2 turn rows + r + s + the return
rail); measured: every one of the 23 rows is load-bearing (rowcut.py). The row
comes out of the READER, 12 interior rows -> 11:

  old: row2 = main loop, ends `v` -> row3 = `]]]` + `Y` -> row4 = tree level 1
  new: row2 = main loop *westward*, ends `Y`      -> row3 = tree level 1

`Y` places its copies at rot_cw(dir) and rot_ccw(dir) of the PARENT's heading
(interp/src/lib.rs:1084). A southbound splitter therefore throws both copies
sideways, and the demux copy needs a `v` cell to face south again -- that cell
is the whole of old row 3. Splitting from a WESTBOUND man instead throws the
copies north and south, so the demux copy is born already facing south and the
cell it is born on can be tree level 1 itself. The three `]` that prepared
BP=seq>>3 move into row 2's glide, ahead of the fork.

The returning (north) copy now runs east along row 1 and, on the way, computes
what it sends to the checker. It sends `8 - seq` rather than `-seq`:

    W   A<->B   (A=1, B=seq)      B held 1 for the tree's `&`
    8   A=8
    -   A=8-seq

so the checker's window invariant becomes B = Wt + 8 and its init collapses
from `4 M * M` to `8 M`. `1 M` after the send restores B=1 for the next fork,
and the startup man walks the same row -- his spurious `8` reaches the checker
as A = 8 + 8 = 16 > 0, i.e. an accepted arrival that changes no state.

Right-band placement comes from scratchpad/tcpwork/bandsearch.py, which
enumerates every legal (checker, I room, O room, 4 pipes) packing. At width 22
it needs a 13-row checker, which is why `H` is dropped here (measured free: the
overflow man's wall crash happens after the final output).

STATUS: 22x22, box 484. The READ RACE IS SOLVED -- measured: the demux clone
takes the packet value at tick 52, the loop man takes the next seq at 61, and
the first round outputs 100 correctly. The fix was to stop treating the ring
length as a bound: rows 3 and 4 have free WESTERN columns (the tree only starts
at col 3-5 there), so the loop dips (1,2)->(1,3)->(1,4)->(2,4)->(2,3)->(2,2)
before turning east, buying 4 ticks on the hot path. Loop `r` moves from T+12 to
T+16 against a clone that needs T+13.

It now fails on a SECOND, independent constraint: pipe binding. `s` picks the
nearest OUTGOING pipe, and every reader cell has a lane pipe directly below it
at distance (13-y). The seq pipe can only be reached from the reader's EAST
half -- measured, the seq send must sit at col >=7 (col 6 ties). The dip puts
the loop man's leg in cols 8..1, so its `s` lands at col 5 and the seq stream
is written into lane 5 instead of the checker.

It reduces to an exact dichotomy, both halves machine-verified. The checker's
init cells are the column-R cells between the ok-return turn row and the `@`
row -- i.e. exactly alongside the overflow gadget -- so **init cells = overflow
rows**. A 4th init cell and a 14th checker row are the same object:

  keep `H`  -> overflow 4 rows -> 4 init cells -> B=16 (`4M*M`) -> K=16
            -> reader needs only `N`, so `s` lands at col 7 -> BINDING WINS
            -> but bandsearch: a 14-row checker has NO PLACEMENT at width 22.

  drop `H`  -> 13-row checker, which DOES pack (bandsearch, cy=8)
            -> 3 init cells -> initsearch.py brute-forces every 3-cell program
               over the real op set: max reachable B is 9, and 16 needs 4 cells
            -> K<=9 -> reader must supply c = 16-K >= 7 -> that needs 3 ops
               (stash seq in B, load the constant, subtract); 2 ops reach only
               c in {0,+1,-1} -> `s` lands at col 5.
            -> binding needs col >=6 (col 6 ties, and reading order resolves the
               tie in seq's favour since (18,1) precedes (6,13)). One short.

The `s` cannot move east instead: the transform must run AFTER the fork (A must
still be seq at `Y` for the tree's `b` reloads and its `&`), the return leg runs
cols 8..1, and (9,1) is a one-way valve -- a man cannot cross back west past `Y`,
since rows 3/5/7 are all blocked mid-span by tree cells. Putting `s` before the
fork at (8,2) binds fine but then the checker sees raw seq, which still needs
K=16 and so the 4th init cell again.

"""
import sys

W, H = 22, 22
CX, CY = 18, 8                       # checker: cols 18..21, rows 8..20
RH = 13                              # reader rows 0..12

# reader interior rows 1..11, cols 1..16.
READER = [
    "v M1s-8W<      <",             # 1  return leg, runs WEST back to col 1
    " > rb]]]Y@r0   ^",             # 2  main loop runs EAST into the fork at col 9
    "    v]]bxb]]v   ",             # 3  level 1  (the copy is born on the `x`)
    ">^vbxbv   vbxbv ",             # 4  level 2 -- cols 1-2 are the loop's dip
    "  ]   ]   ]   ] ",             # 5  reload shift
    " vxv vxv vxv vxv",             # 6  level 3
    " & & & & & & & &",             # 7  isolate bit 0
    "vXvXvXvXvXvXvXvX",             # 8  level 4
    "rrrrrrrrrrrrrrrr",             # 9  read the packet value
    "ssssssssssssssss",             # 10 write it into the lane pipe
    "HHHHHHHHHHHHHHHH",             # 11 retire the demux man
]
SWEEPER = [
    "v<v<v<v<v<v<v<v<",
    "rsrsrsrsrsrsrsrs",
    "srsrsrsrsrsrsrsr",
    "v^<^<^<^<^<^<^<^",
    ">@             ^",
]
# checker_x3 with K=8: the init chain is `8 M` instead of `4 M * M`.
CHK_L = ">1sU+ba1Ns@"                # no `H`: the overflow man walks into the
CHK_R = "v+M<  ^ M8^"                # south wall AFTER the final output (free)


def main(out='/tmp/tcp22.man'):
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

    # --- reader, lane pipes, sweeper (cols 0..17) ---
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

    # --- checker (cols 18..21, rows 7..20), U in col 19 ---
    for j, ch in enumerate(CHK_L):
        put(CX + 1, CY + 1 + j, ch)
    for j, ch in enumerate(CHK_R):
        put(CX + 2, CY + 1 + j, ch)
    room(CX, CY, 4, 13)

    # --- I/O rooms and the four pipes (bandsearch.py) ---
    room(18, 0, 3, 3); put(19, 1, 'I')           # I room, cols 18..20 rows 0..2
    room(19, 3, 3, 3); put(20, 4, 'O')           # O room, cols 19..21 rows 3..5
    for y in (3, 4, 5):                          # input -> reader east wall (17,6)
        put(18, y, 'v')
    put(18, 6, '<')
    put(18, 7, '>'); put(19, 7, 'v')             # seq   -> checker north wall
    put(18, 21, '>'); put(19, 21, '^')           # drain -> checker south wall
    put(20, 7, '^'); put(20, 6, '^')             # output -> O room south wall

    txt = '\n'.join(''.join(r).rstrip() for r in g).rstrip('\n') + '\n'
    open(out, 'w').write(txt)
    ls = txt.rstrip('\n').split('\n')
    ww = max(len(r) for r in ls)
    xs = [x for x in range(ww) if any(len(r) > x and r[x] != ' ' for r in ls)]
    ys = [i for i, r in enumerate(ls) if r.strip()]
    bw, bh = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    print(f'wrote {out}  {bw}x{bh}  box {max(bw, bh) ** 2}')


main(*sys.argv[1:2])
