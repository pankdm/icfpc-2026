"""16-way demux in 7 rows (emit_montree spends 12), same leaf columns.

emit_montree costs 3 rows per level -- literal `w`, `&`, `X` -- and the `X`'s
glide only exists on the SET branch, so nothing can ride it: the CLEAR branch
walks straight down an empty column and it is the clear branch that fixes the
row count.

`x` is a two-way branch in ONE cell (CW if BP's low bit is 1, else CCW) and it
leaves A and B alone, so BOTH branches glide and the glides become free real
estate for the next level's ops.

The trap is bit ORDER.  `x` reads BP's low bit, so the cheap order is LSB-first
with no reloads -- but then the level magnitudes must be 1,2,4 (INCREASING), and
a level's glide then runs over its own siblings' cells in the same row.  Not a
routing accident: with bit0 first the two subtrees own INTERLEAVED leaf sets, so
their column ranges cannot be disjoint.

MSB-first restores a properly nested tree (contiguous halves, magnitudes 4,2,1,
glides never leave their own block).  It costs a `b`+`]`^k reload per level --
and those reloads ride the glides, which at the top are exactly wide enough:

    level 1 (bit3)  glide 4 -> 3 free cells: `b` `]` `]`   -> free
    level 2 (bit2)  glide 2 -> 1 free cell:  `b`, and `]`  -> 1 row
    level 3 (bit1)  glide 1 -> 0 free cells: `&` `b`       -> 2 rows
    level 4 (bit0)  `d` on BP>0, displacement 0 or -1

    rows: x | x | ] | x | & | b | d   = 7, then the leaf row

No masking is needed: `x` reads the LOW BIT of BP, so BP = seq>>3 tests bit3 of
seq directly however large seq is.  Only the last level needs `seq & 1`, so B
holds the single constant 1 and A holds seq untouched the whole way down
(`b`, `]`, `x` write neither).

Displacements +4/-4, +2/-2, +1/-1, 0/-1 give leaf = R + 7 - slot, i.e. exactly
emit_montree's `entry_col - slot` with R = entry_col - 7. The sweeper, the lane
pipes and the leaf ops are all unchanged.
"""


def emit_xtree(L, R, y0):
    """Man arrives at (R,y0) heading SOUTH with A=seq, B=1, BP=seq>>3.

    Returns {slot: leaf_col}; the leaf row is y0+7.
    """
    lvl1 = [R]
    # ---- row y0: bit3, +-4, carrying `b` `]` `]` (BP = seq>>2) ----
    for c in lvl1:
        L.put(c, y0, 'x')
        for s in (+1, -1):
            L.put(c + 1 * s, y0, 'b')
            L.put(c + 2 * s, y0, ']')
            L.put(c + 3 * s, y0, ']')
            L.put(c + 4 * s, y0, 'v')
    lvl2 = [c + 4 * s for c in lvl1 for s in (+1, -1)]

    # ---- row y0+1: bit2, +-2, carrying `b`; the `]` needs its own row ----
    for c in lvl2:
        L.put(c, y0 + 1, 'x')
        for s in (+1, -1):
            L.put(c + 1 * s, y0 + 1, 'b')
            L.put(c + 2 * s, y0 + 1, 'v')
    lvl3 = [c + 2 * s for c in lvl2 for s in (+1, -1)]

    # ---- row y0+2: `]`  (BP = seq>>1) ----
    for c in lvl3:
        L.put(c, y0 + 2, ']')

    # ---- row y0+3: bit1, +-1 (glide 1: no free cells) ----
    for c in lvl3:
        L.put(c, y0 + 3, 'x')
        for s in (+1, -1):
            L.put(c + 1 * s, y0 + 3, 'v')
    lvl4 = [c + 1 * s for c in lvl3 for s in (+1, -1)]

    # ---- rows y0+4/y0+5: `&` `b`  (BP = seq & 1, B == 1) ----
    for c in lvl4:
        L.put(c, y0 + 4, '&')
        L.put(c, y0 + 5, 'b')

    # ---- row y0+6: bit0 via `d` (BP>0 -> CW = west by 1; else straight) ----
    for c in lvl4:
        L.put(c, y0 + 6, 'd')
        L.put(c - 1, y0 + 6, 'v')

    return {s: R + 7 - s for s in range(16)}


def _walk(R, y0, grid, seq):
    """Replay the decode on the emitted cells; returns the leaf column."""
    x, y, d = R, y0, (0, 1)
    a, b, bp = seq, 1, seq >> 3
    for _ in range(400):
        g = grid.get((x, y), ' ')
        if g == 'x':
            d = (-d[1], d[0]) if (bp & 1) else (d[1], -d[0])
        elif g == 'd':
            if bp > 0:
                d = (-d[1], d[0])
        elif g == 'b':
            bp = a
        elif g == ']':
            bp >>= 1
        elif g == '&':
            a &= b
        elif g == 'v':
            d = (0, 1)
        elif g == ' ':
            pass
        else:
            raise AssertionError(f"unexpected {g!r} at {(x, y)}")
        x, y = x + d[0], y + d[1]
        if y == y0 + 7:
            return x
    raise AssertionError("no leaf")


def selftest():
    cells = {}

    class _G:
        def put(self, x, y, ch):
            if (x, y) in cells and cells[(x, y)] != ch:
                raise AssertionError(f"collision at {(x,y)}: {cells[(x,y)]!r} vs {ch!r}")
            cells[(x, y)] = ch
    R, y0 = 100, 0
    leaves = emit_xtree(_G(), R, y0)
    for seq in range(0, 96):
        got = _walk(R, y0, cells, seq)
        want = leaves[seq & 15]
        assert got == want, f"seq={seq} slot={seq&15}: leaf {got} != {want}"
    cols = sorted(leaves.values())
    assert cols == list(range(R - 8, R + 8)), cols
    print(f"xtree OK: 16 contiguous leaves {cols[0]}..{cols[-1]}, 7 rows, no collisions")


if __name__ == '__main__':
    selftest()
