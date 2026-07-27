# P6: same M/P/O/I layout as p5v2 (17x17, box 289); C rebuilt.
#
# C redesign (measured: old C was the bottleneck at 22.9 ticks/char, zero stalls):
#  * B is PARKED at 5 for the whole run, so the type is one op `}` (A = ascii>>5)
#    instead of the old `b M 5 W }` five-cell sequence.
#  * opener/closer is ONE branch instead of a nested pair:
#        BP = ascii; m -> ascii-1; ] -> (ascii-1)>>1; bit0 == 1 iff OPENER
#        ( 40->19  ) 41->20  [ 91->45  ] 93->46  { 123->61  } 125->62
#  * `U` receives AND faces east (the I->C pipe flows east), so the receive sits
#    on a corner the walk already needs.
#  * the hot path is a bare 2x5 ring: q d U b m ] x < } s  -> 10 ticks/opener.
#    closers leave the ring at `x` for } N s and rejoin at `q`      -> 14 ticks.
import os as _os, sys
_REPO = _os.path.abspath(__file__).split('/solutions/')[0]
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# --- C: cells are (x, y) local to the room box (walls at 0 and W-1 / H-1) ---
# room is 12x6 at (5,11); local (1,1) == grid (6,12)
C_CELLS = [
 # row 12: idle-ring top + closer return leg (westbound)
 (1,1,'v'),(2,1,'s'),(3,1,'<'),(5,1,'0'),(6,1,'a'),(7,1,'q'),(8,1,'s'),(9,1,'N'),(10,1,'<'),
 # row 13: closer's shift-to-type cell
 (10,2,'}'),
 # row 14: idle-ring right + B=5 park + hot compute leg (eastbound)
 (2,3,'v'),(3,3,'X'),(4,3,'5'),(5,3,'M'),(6,3,'U'),(7,3,'b'),(8,3,'m'),(9,3,']'),(10,3,'x'),
 # row 15: idle-ring bottom + opener return leg (westbound)
 (1,4,'>'),(2,4,'U'),(3,4,'^'),(5,4,'0'),(6,4,'d'),(7,4,'q'),(8,4,'s'),(9,4,'}'),(10,4,'<'),
]
C_MAN = (1,3)
C_W, C_H = 12, 6

M9_CELLS = [
 (1,1,'>'),(2,1,'s'),(3,1,'v'),(4,1,'<'),(5,1,'W'),(7,1,'<'),
 (1,2,'+'),(3,2,'M'),(7,2,'s'),(8,2,'>'),(9,2,'v'),
 (1,3,'+'),(3,3,'r'),(6,3,'>'),(7,3,'1'),(8,3,'^'),(9,3,'r'),
 (1,4,'^'),(2,4,'+'),(3,4,'X'),(4,4,'+'),(5,4,'M'),(6,4,'X'),(7,4,'^'),(8,4,'^'),(9,4,'M'),
 (3,5,'W'),(6,5,'3'),(7,5,'d'),(8,5,'^'),(9,5,'*'),
 (1,6,'v'),(2,6,'2'),(3,6,'X'),(6,6,'W'),(7,6,'b'),(8,6,'^'),(9,6,'X'),
 (1,7,'N'),(3,7,'s'),(6,7,'/'),(7,7,'W'),
 (1,8,'s'),(3,8,'>'),(4,8,'^'),(6,8,'>'),(7,8,'^'),
 (1,9,'>'),(2,9,'0'),(3,9,'M'),(4,9,'^'),(5,9,'0'),(6,9,'s'),(7,9,'N'),(8,9,'2'),(9,9,'<'),
]
M9_MAN = (6,1)
M9_W, M9_H = 11, 11

P_CELLS = [
 (1,1,'>'),(2,1,'s'),(3,1,'0'),(4,1,'v'),
 (1,2,'+'),(2,2,'>'),(3,2,'0'),(4,2,'v'),
 (1,3,'1'),(2,3,'s'),(4,3,'M'),
 (1,4,'^'),(2,4,'X'),(3,4,'1'),(4,4,'v'),
 (2,5,'r'),(4,5,'+'),
 (2,6,'^'),(3,6,'M'),(4,6,'<'),
]
P_MAN = (1,6)
P_W, P_H = 6, 8


def block(p, ox, oy, w, h, cells, man):
    p.room(ox, oy, w, h)
    for (x, y, ch) in cells:
        k = (ox + x, oy + y)
        assert p.cells.get(k) in (None, ch), f'collision {k}: {p.cells.get(k)} vs {ch}'
        p.put(ox + x, oy + y, ch)
    p.man(ox + man[0], oy + man[1])


def build(save):
    p = lm.Program()
    mw = M9_W
    block(p, 0, 0, M9_W, M9_H, M9_CELLS, M9_MAN)
    px = mw
    block(p, px, 0, P_W, P_H, P_CELLS, P_MAN)
    p.put(px, 8, '>'); p.put(px + 1, 8, '^')
    p.output_room(px + 3, 8)
    p.put(px + 2, 8, 'v'); p.put(px + 2, 9, '>')
    block(p, mw - 6, 11, C_W, C_H, C_CELLS, C_MAN)
    cx = mw - 6
    p.put(cx - 1, 12, '<'); p.put(cx - 2, 12, '^'); p.put(cx - 2, 11, '^')
    p.input_room(cx - 5, 13)
    p.put(cx - 2, 14, '>'); p.put(cx - 1, 14, '>')
    print('footprint', p.footprint())
    p.save(save)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:]]
    build(args[0] if args else '/tmp/p6.man')
