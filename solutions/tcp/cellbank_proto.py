"""Stage-2 proof: decode-addressed cell bank (WRITE path).
Courier loop reads [mode,addr,val] from input; BP=addr steers the x/] tree to the
addr-th leaf; leaf sends [mode,val] E to cell[addr]'s IN pipe. Cell does r r M
(discard mode, store val in B). Verify: after a sequence of writes, each cell man's
B == the last value written to that address, and NO crosstalk. Verified by reading
cell men's B from the oracle snapshot.
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from layout import Layout, auto_pipe

NBITS = 2
NCELL = 1 << NBITS
W = [3 * (1 << (NBITS - 1 - i)) for i in range(NBITS)]   # pitch-6 leaves -> straight cell pipes
R0 = sum(W) + 4
XC = [10 + 2 * i for i in range(NBITS)]
SENDC = XC[-1] + 2              # leaf send start column (W s W s)
RETC = SENDC + 5               # riser column (interior)
EASTW = RETC + 2               # tree room east wall column
TRAIL = R0 - sum(W) - 2        # top return-rail row (above the whole tree)


def leaf_row(slot):
    off = 0
    for i in range(NBITS):
        off += W[i] if ((slot >> i) & 1) else -W[i]
    return R0 + off


def build():
    L = Layout()
    top, bot = 1, R0 + sum(W) + 2
    L.room(0, top, EASTW + 1, bot - top + 1)
    # input west -> west wall row R0
    L.input_room(-5, R0 - 1)
    L.pipe([(-2, R0), (-1, R0)])

    # preamble row R0:  @ > r(mode) M r(addr) b r(val)   x-tree at XC[0]
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
                # leaf on row `corner`, heading E: A=val B=mode -> W s W s
                L.put(SENDC, corner, 'W'); L.put(SENDC + 1, corner, 's')
                L.put(SENDC + 2, corner, 'W'); L.put(SENDC + 3, corner, 's')
                L.put(RETC, corner, '^')          # rise to top rail
    node(0, XC[0], R0)

    # top return rail: (RETC,TRAIL) turn W, W to (2,TRAIL) turn S, down col2 to (2,R0)='>'
    L.put(RETC, TRAIL, '<')
    L.put(2, TRAIL, 'v')                          # comes down col2 into (2,R0) '>'

    # cells at EXACT leaf rows (pitch 6) -> straight E IN pipes, zero crossings.
    CX = EASTW + 4                                 # cell west-wall column
    cells = {}
    for s in range(NCELL):
        lr = leaf_row(s)
        L.room(CX, lr - 1, 9, 4)                   # interior rows lr, lr+1
        L.put(CX + 1, lr, '@'); L.put(CX + 2, lr, '>')
        L.put(CX + 3, lr, 'r'); L.put(CX + 4, lr, 'r'); L.put(CX + 5, lr, 'M'); L.put(CX + 6, lr, 'v')
        L.put(CX + 2, lr + 1, '^'); L.put(CX + 6, lr + 1, '<')
        cells[s] = (CX, lr)
        L.pipe([(EASTW + 1, lr), (CX - 1, lr)])    # straight E: tree east wall -> cell west wall
    return L, cells


if __name__ == '__main__':
    L, cells = build()
    print(L.render())
    print('FOOT', L.footprint())
    print('slot->leafrow', {s: leaf_row(s) for s in range(NCELL)})
    print('cells entry', cells)
    L.save('/Users/visenbaev/icfpc26/scratchpad/cellbank.man')
