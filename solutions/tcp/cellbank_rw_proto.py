"""Stage-2.5: full decode-addressed cell bank (WRITE + READ round-trip).
One decoder, courier carries A=val, B=mode(1=write/0=read), BP=addr. Leaf sends
[mode,val] to cell[addr]. Cell branches on mode:
  write: r(val) M          -> B=val stored
  read : r(dummy) W s W    -> send stored B to collector -> O   (B preserved)
Collector R-merges the 16 OUT pipes -> O. Proves random-access read+write.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout

NBITS = 2
NCELL = 1 << NBITS
W = [4 * (1 << (NBITS - 1 - i)) for i in range(NBITS)]   # pitch-8 leaves
R0 = sum(W) + 6
XC = [10 + 2 * i for i in range(NBITS)]
SENDC = XC[-1] + 2
RETC = SENDC + 5
EASTW = RETC + 2
TRAIL = R0 - sum(W) - 2


def leaf_row(slot):
    off = 0
    for i in range(NBITS):
        off += W[i] if ((slot >> i) & 1) else -W[i]
    return R0 + off


def build():
    L = Layout()
    top, bot = 1, R0 + sum(W) + 3
    L.room(0, top, EASTW + 1, bot - top + 1)
    L.input_room(-5, R0 - 1)
    L.pipe([(-2, R0), (-1, R0)])
    # preamble:  @ > r(mode) M r(addr) b r(val)
    L.put(1, R0, '@'); L.put(2, R0, '>')
    L.put(3, R0, 'r'); L.put(4, R0, 'M'); L.put(5, R0, 'r'); L.put(6, R0, 'b'); L.put(7, R0, 'r')

    def node(level, col, row):
        L.put(col, row, 'x')
        for bit in (1, 0):
            sign = +1 if bit == 1 else -1
            w = W[level]
            if level < NBITS - 1:
                L.put(col, row + sign, ']')
            corner = row + sign * w
            L.put(col, corner, '>')
            if level < NBITS - 1:
                node(level + 1, XC[level + 1], corner)
            else:
                L.put(SENDC, corner, 'W'); L.put(SENDC + 1, corner, 's')
                L.put(SENDC + 2, corner, 'W'); L.put(SENDC + 3, corner, 's')
                L.put(RETC, corner, '^')
    node(0, XC[0], R0)
    L.put(RETC, TRAIL, '<'); L.put(2, TRAIL, 'v')

    # cells at exact leaf rows. interior rows lr..lr+3 (room 6 tall). straight IN/OUT pipes.
    CX = EASTW + 4
    EW = CX + 10                 # cell east wall col
    cells = {}
    for s in range(NCELL):
        lr = leaf_row(s)
        L.room(CX, lr - 1, 11, 6)
        # entry row lr:  @ > r X  r W s W v
        L.put(CX + 1, lr, '@'); L.put(CX + 2, lr, '>'); L.put(CX + 3, lr, 'r'); L.put(CX + 4, lr, 'X')
        L.put(CX + 5, lr, 'r'); L.put(CX + 6, lr, 'W'); L.put(CX + 7, lr, 's'); L.put(CX + 8, lr, 'W'); L.put(CX + 9, lr, 'v')
        # write branch (X CW -> S) col CX+4:  r  M
        L.put(CX + 4, lr + 1, 'r'); L.put(CX + 4, lr + 2, 'M'); L.put(CX + 4, lr + 3, '<')
        # read branch riser down col CX+9 to rail lr+3
        L.put(CX + 9, lr + 3, '<')
        # return rail row lr+3 -> W to CX+2 -> up to '>'
        L.put(CX + 2, lr + 3, '^')
        cells[s] = (CX, lr)
        L.pipe([(EASTW + 1, lr), (CX - 1, lr)])            # IN straight
    return L, cells, CX, EW


def add_collector(L, cells, CX, EW):
    # collector east of cells: R-merge 4 OUT pipes -> O below.
    rows = sorted(leaf_row(s) for s in range(NCELL))
    COLX = EW + 4
    ctop, cbot = rows[0] - 1, rows[-1] + 2
    L.room(COLX, ctop, 7, cbot - ctop + 1)
    # racetrack: @ > R v / ^ s <   near top
    my = rows[0]
    L.put(COLX + 1, my, '@'); L.put(COLX + 2, my, '>'); L.put(COLX + 3, my, 'R'); L.put(COLX + 4, my, 'v')
    L.put(COLX + 2, my + 1, '^'); L.put(COLX + 3, my + 1, 's'); L.put(COLX + 4, my + 1, '<')
    # OUT pipes: each cell east wall (EW,lr) -> collector west wall (COLX,lr)
    for s in range(NCELL):
        lr = leaf_row(s)
        L.pipe([(EW + 1, lr), (COLX - 1, lr)])
    # O below collector; collector south wall -> O
    ocol = COLX + 3
    L.output_room(ocol - 1, cbot + 3)
    L.pipe([(ocol, cbot + 1), (ocol, cbot + 2)])
    return L


if __name__ == '__main__':
    L, cells, CX, EW = build()
    add_collector(L, cells, CX, EW)
    print(L.render())
    print('FOOT', L.footprint())
    print('slot->leafrow', {s: leaf_row(s) for s in range(NCELL)})
    L.save(_REPO + '/scratchpad/cellbank_rw.man')
