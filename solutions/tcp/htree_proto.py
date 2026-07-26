"""Fold step: H-tree decoder. 2 vertical splits (bits 0,1 -> 4 band rows) then
2 horizontal splits (bits 2,3 -> 4 columns) => 16 leaves in a compact 4x4 grid.
Each leaf ends in H at a distinct (col,row); we verify the 16-way bijection on
the oracle (final runner position).

V-phase reuses the stage-1 vertical tree (re-orient to E between levels).
H-phase: man heading S, x deflects W/E, re-orient to S between levels.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout

WV = [10, 5]          # vertical weights -> bands spaced 10
WH = [12, 6]          # horizontal weights -> cols spaced 12
R0 = 20               # entry row
XV = [6, 8]           # vertical x-columns
XH = 22               # column where man turns S to start H-phase
HROW = 1              # rows below band exit where level-2 H-x sits


def leaf_pos(slot):
    # V-phase: bits 0,1 -> row. from E: bit1 CW->S(+), bit0 CCW->N(-)
    b0, b1, b2, b3 = [(slot >> i) & 1 for i in range(4)]
    row = R0 + (WV[0] if b0 else -WV[0]) + (WV[1] if b1 else -WV[1])
    # H-phase: from S: bit1 CW->W(-), bit0 CCW->E(+)
    col = XH + (-WH[0] if b2 else WH[0]) + (-WH[1] if b3 else WH[1])
    return col, row + 3      # leaf mouth 3 rows below band exit


def build():
    L = Layout()
    top, bot = R0 - 20, R0 + 20
    left, right = -2, XH + WH[0] + WH[1] + 3
    L.room(left, top, right - left + 1, bot - top + 1)
    L.input_room(left - 5, R0 - 1)
    L.pipe([(left - 2, R0), (left - 1, R0)])
    L.put(left + 1, R0, '@'); L.put(left + 2, R0, 'r'); L.put(left + 3, R0, 'b')

    def node_v(level, col, row):
        L.put(col, row, 'x')
        for bit in (1, 0):
            sign = +1 if bit == 1 else -1          # bit1 CW->S(down)
            w = WV[level]
            L.put(col, row + sign, ']')            # shift after every V level (bits 0 and 1)
            corner = row + sign * w
            L.put(col, corner, '>')                # re-orient E
            if level < 1:
                node_v(level + 1, XV[level + 1], corner)
            else:
                start_h(corner)                    # band exit: man heading E at row=corner

    def start_h(brow):
        # travel E from XV[1] to XH, turn S
        L.put(XH, brow, 'v')
        node_h(0, XH, brow + 1)

    def node_h(level, col, row):
        L.put(col, row, 'x')
        for bit in (1, 0):
            sign = -1 if bit == 1 else +1          # from S: bit1 CW->W(-), bit0 CCW->E(+)
            w = WH[level]
            if level < 1:
                L.put(col + sign, row, ']')
            corner = col + sign * w
            L.put(corner, row, 'v')                # re-orient S
            if level < 1:
                node_h(level + 1, corner, row + 1)
            else:
                L.put(corner, row + 1, 'H')        # leaf: halt at mouth

    node_v(0, XV[0], R0)
    return L


if __name__ == '__main__':
    L = build()
    print(L.render())
    print('FOOT', L.footprint())
    print('leaf positions:', {s: leaf_pos(s) for s in range(16)})
    print('distinct:', len(set(leaf_pos(s) for s in range(16))) == 16)
    L.save(_REPO + '/scratchpad/htree.man')
