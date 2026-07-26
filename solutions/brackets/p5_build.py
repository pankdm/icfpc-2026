# P5: composite repack of p4 pipeline. Same C and M interiors as p4; P reshaped
# from 7x9 (interior 5x7) to 6x8 (interior 4x6, rotated 3-branch loop, spine heads N,
# trigger loop 8 ticks). C moved flush under M (touching walls), C->M pipe rerouted
# around the SW corner; O tucked between P-south and C-top on the east edge.
# Stage A (--wide): M kept 12x11 -> grid 18x17 (box 324).
# Stage B: M reshaped to 11 wide -> grid 17x17 (box 289).
import os as _os, sys
_REPO = _os.path.abspath(__file__).split('/solutions/')[0]
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

C_CELLS = [
 (1,1,'v'),(2,1,'<'),(6,1,'<'),(8,1,'s'),(9,1,'N'),(10,1,'<'),
 (1,2,'q'),(2,2,'^'),(7,2,'s'),(8,2,'x'),(9,2,']'),(10,2,'x'),
 (1,3,'a'),(2,3,'r'),(3,3,'b'),(4,3,'M'),(5,3,'5'),(6,3,'W'),(7,3,'}'),(8,3,'^'),(10,3,']'),
 (1,4,'>'),(2,4,'0'),(3,4,'s'),(5,4,'r'),(6,4,'^'),(8,4,'^'),(10,4,'<'),
]
C_MAN = (4,4)
C_W, C_H = 12, 6

M_CELLS = [
 (1,1,'>'),(2,1,'s'),(3,1,'v'),(4,1,'<'),(5,1,'<'),(7,1,'W'),(8,1,'<'),
 (1,2,'+'),(3,2,'M'),(8,2,'s'),
 (1,3,'+'),(3,3,'r'),(6,3,'>'),(8,3,'1'),(9,3,'>'),(10,3,'v'),
 (1,4,'^'),(2,4,'+'),(3,4,'X'),(4,4,'+'),(5,4,'M'),(6,4,'X'),(7,4,'>'),(8,4,'^'),(10,4,'v'),
 (3,5,'W'),(6,5,'3'),(7,5,'d'),(8,5,'>'),(9,5,'^'),(10,5,'r'),
 (1,6,'v'),(2,6,'2'),(3,6,'X'),(6,6,'W'),(7,6,'b'),(10,6,'M'),
 (1,7,'N'),(3,7,'s'),(6,7,'/'),(7,7,'W'),(10,7,'*'),
 (1,8,'s'),(3,8,'>'),(4,8,'^'),(6,8,'>'),(7,8,'^'),(9,8,'^'),(10,8,'X'),
 (1,9,'>'),(2,9,'0'),(3,9,'M'),(4,9,'^'),(5,9,'^'),(6,9,'0'),(7,9,'s'),(8,9,'N'),(9,9,'2'),(10,9,'<'),
]
M_MAN = (6,1)
M_W, M_H = 12, 11

# Stage B: M interior re-laid on 9x9 (outer 11x11). Drain loop folded to cols 8-9
# (spine v,r,M,*,X down col9; return ^^^,> up col8), send-1 path on col 7 (^,1,s,<)
# with the quot/1 'W' swap moved to (5,1); offense entry via row 3; drain verdict
# row 9 rejoins the shared col-4 return.
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

# New P: interior 4x6. Spine col2 heading N (^ r X); trigger E (1,v,+,<,M);
# balanced straight (s,>,0,v,M shared tail); offense W (^,1,+,>,s,0,v shared tail).
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
    for (x,y,ch) in cells:
        k = (ox+x, oy+y)
        assert p.cells.get(k) in (None, ch), f'collision {k}: {p.cells.get(k)} vs {ch}'
        p.put(ox+x, oy+y, ch)
    p.man(ox+man[0], oy+man[1])

def build(save, stage='B'):
    p = lm.Program()
    if stage == 'A':
        mw = M_W
        block(p, 0, 0, M_W, M_H, M_CELLS, M_MAN)
    else:
        mw = M9_W
        block(p, 0, 0, M9_W, M9_H, M9_CELLS, M9_MAN)
    px = mw                                        # P west wall flush on M east wall
    block(p, px, 0, P_W, P_H, P_CELLS, P_MAN)
    p.put(px,8,'>'); p.put(px+1,8,'^')             # M->P: under P, into P south wall
    p.output_room(px+3,8)                          # O: 3x3
    p.put(px+2,8,'v'); p.put(px+2,9,'>')           # P->O: into O west wall
    block(p, mw-6, 11, C_W, C_H, C_CELLS, C_MAN)   # C: flush under M, east-aligned
    cx = mw-6
    p.put(cx-1,12,'<'); p.put(cx-2,12,'^'); p.put(cx-2,11,'^')  # C->M around SW
    p.input_room(cx-5,13)                          # I: 3x3
    p.put(cx-2,14,'>'); p.put(cx-1,14,'>')         # I->C: into C west wall
    print('footprint', p.footprint())
    p.save(save)

if __name__ == '__main__':
    stage = 'A' if '--wide' in sys.argv else 'B'
    args = [a for a in sys.argv[1:] if a != '--wide']
    build(args[0] if args else '/tmp/p5.man', stage)
