"""Stage-1: prove the 4-bit computed-turn decoder in isolation.

Man reads one int -> BP=slot, then steers through a 4-level x/] binary tree to one
of 16 leaves. Each leaf ends in H at a distinct (col,row) so the oracle's final
runner position identifies which leaf slot routed to. We verify the 16 slots map
to 16 DISTINCT leaves (a bijection).

Tree: man moves generally EAST; each level's `x` deflects it N/S (vertical binary
tree). weights 8,4,2,1 for bits 0,1,2,3 -> leaf rows R0 + (+/-8 +/-4 +/-2 +/-1).
`]` (BP>>1) placed on the vertical run of levels 0,1,2 (not level 3 - last bit).
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from layout import Layout

W = [8, 4, 2, 1]           # deflection weight per level (bit0..bit3)
R0 = 20                    # center row
XC = [5, 7, 9, 11]         # x-column per level (gap 2)
LEAF_H = 13                # column where leaf places H (east of X3)


def leaf_row(slot):
    off = 0
    for i in range(4):
        bit = (slot >> i) & 1
        off += W[i] if bit else -W[i]
    return R0 + off


def build():
    L = Layout()
    HgtTop, HgtBot = R0 - 16, R0 + 16
    ROOMH = HgtBot - HgtTop + 1
    L.room(0, HgtTop, LEAF_H + 3, ROOMH)   # main room enclosing the tree
    # input room to the west, pipe into west wall at row R0
    L.input_room(-5, R0 - 1)               # I at (-4,R0)
    # pipe from input east wall (-3,R0) into main west wall (0,R0)
    L.pipe([(-2, R0), (-1, R0)])           # 2-cell pipe: back nbr (-3,R0)=I wall, fwd (0,R0)=main wall

    # preamble on row R0: @ r b  then x-tree
    L.put(1, R0, '@'); L.put(2, R0, 'r'); L.put(3, R0, 'b')

    # recursively place the tree. Each node: incoming (col,row) heading E; place x.
    def node(level, col, row):
        L.put(col, row, 'x')
        for bit in (1, 0):                 # bit1 -> CW -> S(down); bit0 -> CCW -> N(up)
            sign = +1 if bit == 1 else -1
            w = W[level]
            # vertical run in this column: ] at first cell (levels 0-2), corner at wth cell
            if level < 3:
                L.put(col, row + sign, ']')
            corner_row = row + sign * w
            L.put(col, corner_row, '>')    # turn back E
            if level < 3:
                nxt_col = XC[level + 1]
                node(level + 1, nxt_col, corner_row)
            else:
                # leaf: head E, place H a couple cells in
                L.put(LEAF_H, corner_row, 'H')
    node(0, XC[0], R0)
    return L


if __name__ == '__main__':
    L = build()
    print(L.render())
    print('FOOT', L.footprint())
    # sanity: bijection of leaf rows
    rows = [leaf_row(s) for s in range(16)]
    print('leaf rows:', rows)
    print('distinct:', len(set(rows)) == 16)
    L.save('/Users/visenbaev/icfpc26/solutions/tcp/decoder16.man')
