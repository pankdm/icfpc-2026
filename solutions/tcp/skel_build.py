"""Skeleton: controller forwards input[seq,val] -> CMD_WRITE(seq&15,val);
CMD_READ(seq&15) to driver -> cell -> collector -> O. Validates command-pipe wiring.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout, route
from driver_mod import build_driver

NBITS = 2

def emit_row(L, y, tokens, x0=3):
    """Place tokens L->R on row y from x0. Token: single op char, or ('lit', n)."""
    x = x0
    for t in tokens:
        if isinstance(t, tuple):     # literal
            L.put(x, y, '`'); x += 1
            for ch in str(t[1]):
                L.put(x, y, ch); x += 1
            L.put(x, y, '`'); x += 1
        else:
            L.put(x, y, t); x += 1
    return x

def build():
    L = Layout()
    cmd_pt, o_attach, _ = build_driver(L, NBITS, 48, 2)
    dx, dy = cmd_pt
    # controller room
    CE = 40
    L.room(0, 0, CE + 1, 6)              # small: rows 0..5, ops on row 1, loopback row 2
    # input room left, into west wall row 1
    L.input_room(-5, 0)                  # I at (-4,1); east wall (-3,1)
    L.pipe([(-2, 1), (-1, 1)])
    # cmd pipe: east wall row 1 -> driver cmd_pt
    L.pipe([(CE + 1, 1), (dx - 2, 1), (dx - 2, dy), (dx - 1, dy)])
    # controller man
    L.put(1, 1, '@'); L.put(2, 1, '>')
    toks = ['r','M',('lit',15),'W','&','M',        # A=slot,B=slot
            '1','s','W','s','M','r','s',            # CMD_WRITE(slot,val)
            '0','s','W','s','0','s']                # CMD_READ(slot)
    xend = emit_row(L, 1, toks, x0=3)
    # loopback: (xend,1)->(xend,2)->(2,2)->(2,1)='>'
    route(L, [(xend, 1), (xend, 2), (2, 2), (2, 1)])
    # O room below driver
    ox, oy = o_attach
    L.output_room(ox - 1, oy + 3)
    L.pipe([(ox, oy + 1), (ox, oy + 2)])
    return L

if __name__ == '__main__':
    L = build()
    txt = L.render()
    print(txt)
    L.save(_REPO + '/scratchpad/skel.man')
