"""Standalone 2-stage steer test. Stage1 (heading EAST) uses low K1 bits -> vertical
band. Turn SOUTH. Stage2 (heading SOUTH) uses next K2 bits -> horizontal column.
Each leaf ends in 'H' at a distinct cell. Verify all 2^(K1+K2) addrs -> distinct H."""
import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout

K1 = int(sys.argv[1]) if len(sys.argv) > 1 else 2
K2 = int(sys.argv[2]) if len(sys.argv) > 2 else 2
VP = 3          # vertical pitch
HP = 3          # horizontal pitch
WV = [VP * (1 << (K1 - 1 - i)) for i in range(K1)]
WH = [HP * (1 << (K2 - 1 - j)) for j in range(K2)]
R0 = sum(WV) + 4
XV = [6 + 2 * i for i in range(K1)]     # stage1 x columns
XV_END = XV[-1] + 2                      # where stage1 leaves turn south
RG = 2                                   # stage2 row gap per level


def voff(low):
    o = 0
    for i in range(K1):
        o += WV[i] if ((low >> i) & 1) else -WV[i]
    return o


def final_pos(addr):
    low = addr & ((1 << K1) - 1)
    high = (addr >> K1) & ((1 << K2) - 1)
    row = R0 + voff(low)
    col = XV_END
    for j in range(K2):
        sign = -1 if ((high >> j) & 1) else +1     # bit1->west(CW), bit0->east(CCW)
        col = col + sign * WH[j]
        row = row + (RG if j < K2 - 1 else 1)
    return (col, row)


def build():
    L = Layout()
    # generous room
    poss = [final_pos(a) for a in range(1 << (K1 + K2))]
    minc = min(c for c, r in poss); maxc = max(c for c, r in poss)
    minr = min(r for c, r in poss); maxr = max(r for c, r in poss)
    left = -1; right = maxc + 3
    top = min(minr, R0 - sum(WV)) - 2; bot = maxr + 3
    L.room(0, top, right + 1, bot - top + 1)
    L.input_room(-5, R0 - 1)
    L.pipe([(-2, R0), (-1, R0)])
    L.put(1, R0, '@'); L.put(2, R0, '>'); L.put(3, R0, 'r'); L.put(4, R0, 'b')

    # stage1 vertical tree, heading east
    def s1(level, col, row):
        L.put(col, row, 'x')
        for bit in (1, 0):
            sign = +1 if bit == 1 else -1     # east-heading: CW(bit1)=south=+, CCW(bit0)=north=-
            L.put(col, row + sign, ']')        # ALWAYS shift (2-stage: stage2 needs high bits)
            corner = row + sign * WV[level]
            if level < K1 - 1:
                L.put(col, corner, '>')
                s1(level + 1, XV[level + 1], corner)
            else:
                # end of stage1: turn south into stage2
                L.put(col, corner, '>')       # ensure heading east
                L.put(XV_END, corner, 'v')     # turn south at XV_END
                s2(0, corner + RG if K2 > 1 else corner + 1, XV_END, corner)
    # stage2 horizontal tree, heading south. entry: man heading south at (scol, srow_entry)
    def s2(level, row, col, band_row):
        # man arrives heading south at (col, row-?);  place x at (col,row)
        L.put(col, row, 'x')
        for bit in (1, 0):
            sign = -1 if bit == 1 else +1     # south-heading: CW(bit1)=west=-, CCW(bit0)=east=+
            if level < K2 - 1:
                L.put(col + sign, row, ']')
            corner = col + sign * WH[level]
            if level < K2 - 1:
                L.put(corner, row, 'v')
                s2(level + 1, row + RG, corner, band_row)
            else:
                L.put(corner, row, 'v')        # continue south 1
                L.put(corner, row + 1, 'H')
    s1(0, XV[0], R0)
    return L


if __name__ == '__main__':
    L = build()
    print(L.render())
    print('FOOT', L.footprint())
    fps = {a: final_pos(a) for a in range(1 << (K1 + K2))}
    print('final_pos', fps)
    print('distinct', len(set(fps.values())) == len(fps))
    L.save(_REPO + '/scratchpad/steer2d.man')
