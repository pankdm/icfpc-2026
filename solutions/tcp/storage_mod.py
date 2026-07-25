"""Read+write storage man for the controller (waiting / fmask).
Protocol: controller sends [0] to READ (man replies with B); sends [1,val] to WRITE
(man stores val in B). Man: @ > r X  (read: W s W)  (write CW->S: r M).
IN pipe = controller->man (west wall, row sy). OUT pipe = man->controller (east wall).
build_storage(L, cx, sy) stamps it; returns (in_pt, out_pt) border cells to wire.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout


def build_storage(L, cx, sy):
    L.room(cx, sy - 1, 11, 6)                 # interior rows sy..sy+3
    L.put(cx + 1, sy, '@'); L.put(cx + 2, sy, '>'); L.put(cx + 3, sy, 'r'); L.put(cx + 4, sy, 'X')
    # read branch (mode 0, straight E): W s W  then v down
    L.put(cx + 5, sy, 'W'); L.put(cx + 6, sy, 's'); L.put(cx + 7, sy, 'W'); L.put(cx + 8, sy, 'v')
    # write branch (mode 1, CW->S): r M
    L.put(cx + 4, sy + 1, 'r'); L.put(cx + 4, sy + 2, 'M'); L.put(cx + 4, sy + 3, '<')
    # read riser down col cx+8 to rail
    L.put(cx + 8, sy + 3, '<')
    # return rail sy+3 -> W to cx+2 -> up '>'
    L.put(cx + 2, sy + 3, '^')
    in_pt = (cx, sy)          # west wall
    out_pt = (cx + 10, sy)    # east wall
    return in_pt, out_pt


if __name__ == '__main__':
    # isolated test: tiny controller writes 42 then reads it back -> O
    from layout import route
    L = Layout()
    in_pt, out_pt = build_storage(L, 20, 8)
    # controller room left
    L.room(0, 0, 18, 8)
    L.put(1, 3, '@'); L.put(2, 3, '>')
    # cols: sIN(to storage,out) and rOUT(from storage,in) and O.
    # ops row 3: write 42:  1 s(->storage in) ; then send 42
    toks = ['1', 's', ('lit', 42) if False else '4']  # placeholder
    # simpler: do it by explicit puts across rows
    # row3: c1 ; s(->storage) [mode=1]
    L.put(3, 3, '1'); L.put(4, 3, 's')
    route(L, [(5, 3), (5, 4), (2, 4), (2, 5)]); L.put(1, 5, '>'); L.put(2,5,'>')
    # row5: `42` ; s [val]
    L.put(3, 5, '`'); L.put(4, 5, '4'); L.put(5, 5, '2'); L.put(6, 5, '`'); L.put(7, 5, 's')
    route(L, [(8, 5), (8, 6), (2, 6), (2, 7)]); L.put(1, 7, '>')
    # row7: c0 ; s [mode=0 read] ; r(from storage) ; then send to O
    L.put(3, 7, '0'); L.put(4, 7, 's'); L.put(6, 7, 'r'); L.put(8, 7, 's')  # r=recv storage; last s=to O
    # wait: two outgoing (storage-in, O). nearest ambiguous. Just test read value via snapshot instead.
    # storage in pipe: controller -> storage in_pt
    L.pipe([(18, 3), (19, 3), (19, in_pt[1]), (in_pt[0]-0, in_pt[1])][:-1] + [(in_pt[0]-1, in_pt[1])])
    # storage out pipe: storage out_pt -> controller east wall row 7
    L.pipe([(out_pt[0]+1, out_pt[1]), (out_pt[0]+2, out_pt[1])])
    print(L.render())
