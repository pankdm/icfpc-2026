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
#
# M IS NOW THE BOTTLENECK (15.9 t/char; C is ~11). Measured attempt + why it failed:
# M pop = 22 ticks (29 of 32 pops take it): X + M X 3 W / > ^ W b d ^ 1 s < . W < v M r.
#   * b+d (remainder test) -> a single X is CORRECT and saves an OP, but not a TICK:
#     the freed cell (7,5) sits mid-way up a straight run, and ticks = cells walked.
#   * After W(7,7) B ALREADY holds the quotient, so W(5,1)+M(3,2) are dead weight --
#     but the pop cannot exploit that: r(3,3) must be entered heading SOUTH (it falls
#     through to X(3,4)), and the only cell north of it is M(3,2). Verified by build:
#     returning via row 2 crashes into the west wall.
#   * The 22-cell walk is DISTANCE-MINIMAL for its shape: descent 6,5..6,8 (4) +
#     turnaround (7,8) + ascent 7,7..7,2 (6) + return 7,1..3,3 (7, = 4 west + 2 south + r).
#   * The real unlock is moving the post-offense RESET corridor off column 4 (it pins
#     (4,5)..(4,8) as A==0 pass-throughs, so no pop-only send cell exists there).
#     Free cells for it: (2,2),(2,3),(2,5),(2,7),(2,8).
#   * Sending the quotient before validating (saves the `1`) breaks the offense count
#     by one: P adds 1 on a negative verdict and both offense kinds share verdict -2.
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
