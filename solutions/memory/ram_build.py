"""RAM memory solution: variable-length parse + computed-turn decode tree + cell bank.

Parse per op (variable length): read mode into A; M saves B=mode; X branches:
  mode==0 (READ)  -> X straight (east): read addr, set BP=addr, glide to tree entry.
  mode==1 (WRITE) -> X CW (south) pigtail: read addr (BP), read val (A), rejoin row R0.
Both branches merge at a '>' just west of the tree entry, heading EAST with BP=addr.

Tree steers by BP (x = CW if BP&1 else CCW; ] = BP>>1). N levels -> 2^N leaves.
Leaf sends [mode,val] E to cell[addr]. Cell (@>rXrWsWv racetrack) branches on mode:
  write: r M  -> B := val (stored, persists across loops)
  read : r W s W -> echo stored B to collector -> O   (B preserved)
Courier loops back via top return rail to re-read the next op.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout

NBITS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
NCELL_USED = int(sys.argv[2]) if len(sys.argv) > 2 else (1 << NBITS)
PITCH = 4                                    # vertical cell pitch (rows between leaves)
W = [PITCH * (1 << (NBITS - 1 - i)) for i in range(NBITS)]   # deflection weights
R0 = sum(W) + 6                              # tree center row
XC = [12 + 2 * i for i in range(NBITS)]      # x-node column per level
SENDC = XC[-1] + 2                           # leaf send start col
RETC = SENDC + 5                             # riser col (interior)
EASTW = RETC + 2                             # tree room east wall col
TRAIL = R0 - sum(W) - 3                      # top return rail row
CJOIN = 9                                    # merge col (west of tree)


def leaf_row(slot):
    off = 0
    for i in range(NBITS):
        off += W[i] if ((slot >> i) & 1) else -W[i]
    return R0 + off


def build():
    L = Layout()
    top = min(TRAIL - 1, R0 - sum(W) - 1)
    bot = R0 + sum(W) + 5
    L.room(0, top, EASTW + 1, bot - top + 1)
    L.input_room(-5, R0 - 1)
    L.pipe([(-2, R0), (-1, R0)])

    # preamble row R0: @ > r M X  (mode read + branch)
    L.put(1, R0, '@'); L.put(2, R0, '>')
    L.put(3, R0, 'r'); L.put(4, R0, 'M'); L.put(5, R0, 'X')
    # READ branch (X straight east): r(addr) b(BP)  then glide to CJOIN '>'
    L.put(6, R0, 'r'); L.put(7, R0, 'b'); L.put(CJOIN, R0, '>')
    # WRITE pigtail (X CW -> south at col5): r(addr) b(BP) r(val) then rejoin
    L.put(5, R0 + 1, 'r'); L.put(5, R0 + 2, 'b'); L.put(5, R0 + 3, 'r')
    L.put(5, R0 + 4, '>')                     # head east along row R0+4
    L.put(CJOIN - 1, R0 + 4, '^')             # rise back to R0
    # (CJOIN-1, R0) merge -> east. Put '>' there too so both rejoin then east.
    L.put(CJOIN - 1, R0, '>')

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
    # top return rail
    L.put(RETC, TRAIL, '<'); L.put(2, TRAIL, 'v')

    # cells at exact leaf rows (only the USED slots get a cell)
    CX = EASTW + 4
    EW = CX + 10
    cells = {}
    for s in range(NCELL_USED):
        lr = leaf_row(s)
        L.room(CX, lr - 1, 11, 6)
        L.put(CX + 1, lr, '@'); L.put(CX + 2, lr, '>'); L.put(CX + 3, lr, 'r'); L.put(CX + 4, lr, 'X')
        L.put(CX + 5, lr, 'r'); L.put(CX + 6, lr, 'W'); L.put(CX + 7, lr, 's'); L.put(CX + 8, lr, 'W'); L.put(CX + 9, lr, 'v')
        L.put(CX + 4, lr + 1, 'r'); L.put(CX + 4, lr + 2, 'M'); L.put(CX + 4, lr + 3, '<')
        L.put(CX + 9, lr + 3, '<')
        L.put(CX + 2, lr + 3, '^')
        cells[s] = (CX, lr)
        L.pipe([(EASTW + 1, lr), (CX - 1, lr)])
    return L, cells, CX, EW


def add_collector(L, cells, CX, EW):
    rows = sorted(leaf_row(s) for s in cells)
    COLX = EW + 4
    ctop, cbot = rows[0] - 1, rows[-1] + 2
    L.room(COLX, ctop, 7, cbot - ctop + 1)
    my = rows[0]
    L.put(COLX + 1, my, '@'); L.put(COLX + 2, my, '>'); L.put(COLX + 3, my, 'R'); L.put(COLX + 4, my, 'v')
    L.put(COLX + 2, my + 1, '^'); L.put(COLX + 3, my + 1, 's'); L.put(COLX + 4, my + 1, '<')
    for s in cells:
        lr = leaf_row(s)
        L.pipe([(EW + 1, lr), (COLX - 1, lr)])
    ocol = COLX + 3
    L.output_room(ocol - 1, cbot + 3)
    L.pipe([(ocol, cbot + 1), (ocol, cbot + 2)])
    return L


if __name__ == '__main__':
    L, cells, CX, EW = build()
    add_collector(L, cells, CX, EW)
    print(L.render())
    print('FOOT', L.footprint())
    print('leafrows', {s: leaf_row(s) for s in cells})
    L.save(_REPO + '/scratchpad/ram_lin.man')
