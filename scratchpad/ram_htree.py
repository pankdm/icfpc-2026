"""Full H-tree RAM. Variable parse -> H-tree decode -> cells (staggered distinct rows,
straight-EAST out-pipes to collector, proto-proven) -> collector R-merge -> O.
In-pipe: leaf send -> cell. Cells at distinct rows so out-pipes don't cross."""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from layout import Layout

K1 = int(sys.argv[1]) if len(sys.argv) > 1 else 1   # vertical (low bits)
K2 = int(sys.argv[2]) if len(sys.argv) > 2 else 1   # horizontal (high bits)
NUSED = int(sys.argv[3]) if len(sys.argv) > 3 else (1 << (K1 + K2))
VP = 8
HP = 8
WV = [VP * (1 << (K1 - 1 - i)) for i in range(K1)]
WH = [HP * (1 << (K2 - 1 - j)) for j in range(K2)]
R0 = sum(WV) + 8
XV = [14 + 2 * i for i in range(K1)]
XH0 = XV[-1] + 4       # column where H-phase starts (turn S)
RG = 2


def band_row(low):
    o = 0
    for i in range(K1):
        o += WV[i] if ((low >> i) & 1) else -WV[i]
    return R0 + o


def leaf_col(high):
    col = XH0
    for j in range(K2):
        sign = -1 if ((high >> j) & 1) else +1
        col = col + sign * WH[j]
    return col


def leaf_mouth(addr):
    low = addr & ((1 << K1) - 1)
    high = (addr >> K1) & ((1 << K2) - 1)
    return leaf_col(high), band_row(low) + K2 * RG   # heading south at mouth


def build():
    L = Layout()
    # decoder room bounds
    mouths = [leaf_mouth(a) for a in range(NUSED)]
    dtop = R0 - sum(WV) - 3
    dbot = max(r for c, r in mouths) + 8
    dleft = 0
    dright = XH0 + sum(WH) + 3
    L.room(dleft, dtop, dright - dleft + 1, dbot - dtop + 1)
    L.input_room(-5, R0 - 1)
    L.pipe([(-2, R0), (-1, R0)])

    # --- variable parse preamble ---
    L.put(1, R0, '@'); L.put(2, R0, '>')
    L.put(3, R0, 'r'); L.put(4, R0, 'M'); L.put(5, R0, 'X')
    L.put(6, R0, 'r'); L.put(7, R0, 'b')
    CJ = XV[0] - 2
    L.put(CJ, R0, '>')
    L.put(5, R0 + 1, 'r'); L.put(5, R0 + 2, 'b'); L.put(5, R0 + 3, 'r')
    L.put(5, R0 + 4, '>'); L.put(CJ - 1, R0 + 4, '^'); L.put(CJ - 1, R0, '>')

    # --- H-tree decode ---
    def node_v(level, col, row):
        L.put(col, row, 'x')
        for bit in (1, 0):
            sign = +1 if bit == 1 else -1
            L.put(col, row + sign, ']')             # shift every V level
            corner = row + sign * WV[level]
            L.put(col, corner, '>')
            if level < K1 - 1:
                node_v(level + 1, XV[level + 1], corner)
            else:
                L.put(XH0, corner, 'v')
                node_h(0, XH0, corner + 1)

    def node_h(level, col, row):
        L.put(col, row, 'x')
        for bit in (1, 0):
            sign = -1 if bit == 1 else +1
            if level < K2 - 1:
                L.put(col + sign, row, ']')
            corner = col + sign * WH[level]
            L.put(corner, row, 'v')
            if level < K2 - 1:
                node_h(level + 1, corner, row + 1)
            else:
                place_leaf(corner, row + 1)

    def place_leaf(col, row):
        # heading south: W s W s  sends [mode,val] to cell in-pipe (nearest outgoing)
        L.put(col, row, 'W'); L.put(col, row + 1, 's')
        L.put(col, row + 2, 'W'); L.put(col, row + 3, 's')
        # then return south to bottom rail
        L.put(col, row + 4, 'v')

    node_v(0, XV[0], R0)

    # bottom return rail: gather all leaf drops -> west -> up col2 -> back to '>' at (2,R0)
    railrow = dbot - 1
    for a in range(NUSED):
        c, _ = leaf_mouth(a)
        L.put(c, railrow, '<')   # leaf drop turns west onto rail
    L.put(2, railrow, '^')       # west end: turn north up col2 back to (2,R0)='>'
    # col2 from railrow up to R0 -> '>' already at (2,R0)
    return L, mouths


def add_cells_collector(L, mouths):
    # Cells: proto-style, placed EAST of decoder at DISTINCT rows (staggered), in-pipe from leaf.
    # For this minimal test: cell in-pipe attaches decoder EAST wall at the leaf's row.
    pass  # (wiring added after send-routing is validated)


if __name__ == '__main__':
    L, mouths = build()
    print(L.render())
    print('FOOT', L.footprint())
    print('mouths', {a: leaf_mouth(a) for a in range(NUSED)})
    L.save('/Users/visenbaev/icfpc26/scratchpad/ram_htree_dec.man')
