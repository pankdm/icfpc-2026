"""Driver module: the proven cellbank_rw courier + 16 cells + data-collector -> O,
but the courier is fed by a COMMAND PIPE (from the controller) instead of an input
room. build_driver(L, ox, oy, feed_pt) stamps the driver into layout L with its
top-left near (ox,oy); returns the command-pipe attach point (driver west wall) and
the data-collector -> O attach (so caller wires O). Courier reads [mode,addr,val].
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout


def build_driver(L, NBITS, ox, oy):
    NCELL = 1 << NBITS
    W = [4 * (1 << (NBITS - 1 - i)) for i in range(NBITS)]   # pitch-8
    R0 = oy + sum(W) + 6
    XC = [ox + 10 + 2 * i for i in range(NBITS)]
    SENDC = XC[-1] + 2
    RETC = SENDC + 5
    EASTW = RETC + 2
    TRAIL = R0 - sum(W) - 2

    def leaf_row(slot):
        off = 0
        for i in range(NBITS):
            off += W[i] if ((slot >> i) & 1) else -W[i]
        return R0 + off

    top, bot = oy, R0 + sum(W) + 3
    L.room(ox, top, EASTW + 1 - ox, bot - top + 1)
    cmd_pt = (ox, R0)                       # west wall: command pipe enters here
    # preamble: @ > r(mode) M r(addr) b r(val)
    L.put(ox + 1, R0, '@'); L.put(ox + 2, R0, '>')
    L.put(ox + 3, R0, 'r'); L.put(ox + 4, R0, 'M'); L.put(ox + 5, R0, 'r'); L.put(ox + 6, R0, 'b'); L.put(ox + 7, R0, 'r')

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
    L.put(RETC, TRAIL, '<'); L.put(ox + 2, TRAIL, 'v')

    CX = EASTW + 4
    EW = CX + 10
    cells = {}
    for s in range(NCELL):
        lr = leaf_row(s)
        L.room(CX, lr - 1, 11, 6)
        L.put(CX + 1, lr, '@'); L.put(CX + 2, lr, '>'); L.put(CX + 3, lr, 'r'); L.put(CX + 4, lr, 'X')
        L.put(CX + 5, lr, 'r'); L.put(CX + 6, lr, 'W'); L.put(CX + 7, lr, 's'); L.put(CX + 8, lr, 'W'); L.put(CX + 9, lr, 'v')
        L.put(CX + 4, lr + 1, 'r'); L.put(CX + 4, lr + 2, 'M'); L.put(CX + 4, lr + 3, '<')
        L.put(CX + 9, lr + 3, '<')
        L.put(CX + 2, lr + 3, '^')
        cells[s] = (CX, lr)
        L.pipe([(EASTW + 1, lr), (CX - 1, lr)])

    # data collector: R-merge cell OUTs -> O
    rows = sorted(leaf_row(s) for s in range(NCELL))
    COLX = EW + 4
    ctop, cbot = rows[0] - 1, rows[-1] + 2
    L.room(COLX, ctop, 7, cbot - ctop + 1)
    my = rows[0]
    L.put(COLX + 1, my, '@'); L.put(COLX + 2, my, '>'); L.put(COLX + 3, my, 'R'); L.put(COLX + 4, my, 'v')
    L.put(COLX + 2, my + 1, '^'); L.put(COLX + 3, my + 1, 's'); L.put(COLX + 4, my + 1, '<')
    for s in range(NCELL):
        lr = leaf_row(s)
        L.pipe([(EW + 1, lr), (COLX - 1, lr)])
    o_attach = (COLX + 3, cbot)     # south wall col for O pipe
    return cmd_pt, o_attach, (ctop, cbot)
