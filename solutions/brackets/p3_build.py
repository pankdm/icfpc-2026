# P3: 3-man pipeline for brackets — q-trick reader-classifier (C), stack man (M),
# downstream position-counter/emitter (P). No positions on pipes, no countdown register.
# Protocol: C sends signed codes +-t (t=char>>5) then 0 at end-of-string (q==0), then
# blocks on r(n) for the next round. M keeps stack in B (base-3, digits t, sentinel 0),
# forwards one positive trigger per accepted char, sends verdict 0 (balanced) or -2
# (emit pos+1: covers offense-at-i and unclosed n+1), drains leftovers after offense.
# P counts triggers in B; verdict 0 -> emit 0; negative -> emit pos+1; resets each round.
import os as _os, sys
_REPO=_os.path.abspath(__file__).split('/solutions/')[0]
sys.path.insert(0,_REPO+'/tools')
import littleman as lm

C_CELLS=[
 (1,1,'v'),(2,1,'<'),(6,1,'<'),(8,1,'s'),(9,1,'N'),(10,1,'<'),
 (1,2,'q'),(2,2,'^'),(7,2,'s'),(8,2,'x'),(9,2,']'),(10,2,'x'),
 (1,3,'a'),(2,3,'r'),(3,3,'b'),(4,3,'M'),(5,3,'5'),(6,3,'W'),(7,3,'}'),(8,3,'^'),(10,3,']'),
 (1,4,'>'),(2,4,'0'),(3,4,'s'),(5,4,'r'),(6,4,'^'),(8,4,'^'),(10,4,'<'),
]
C_MAN=(4,4)   # @, faces E into r(5,5)
C_W,C_H=12,6

M_CELLS=[
 (1,1,'>'),(2,1,'s'),(3,1,'v'),(4,1,'<'),(5,1,'<'),(7,1,'W'),(8,1,'<'),
 (1,2,'+'),(3,2,'M'),(8,2,'s'),
 (1,3,'+'),(3,3,'r'),(6,3,'>'),(8,3,'1'),(9,3,'>'),(10,3,'v'),
 (1,4,'^'),(2,4,'+'),(3,4,'X'),(4,4,'+'),(5,4,'M'),(6,4,'X'),(7,4,'>'),(8,4,'^'),(10,4,'v'),
 (3,5,'W'),(6,5,'3'),(7,5,'d'),(8,5,'>'),(9,5,'^'),(10,5,'r'),
 (1,6,'v'),(2,6,'2'),(3,6,'X'),(6,6,'W'),(7,6,'b'),(10,6,'M'),
 (1,7,'N'),(3,7,'s'),(6,7,'/'),(7,7,'W'),(10,7,'*'),
 (1,8,'s'),(3,8,'>'),(4,8,'^'),(6,8,'>'),(7,8,'^'),(9,8,'^'),(10,8,'X'),
 (1,9,'>'),(2,9,'0'),(3,9,'M'),(4,9,'^'),(10,9,'2'),
 (5,10,'^'),(7,10,'0'),(8,10,'s'),(9,10,'N'),(10,10,'<'),
]
M_MAN=(6,1)
M_W,M_H=12,12

P_CELLS=[
 (3,1,'v'),(3,2,'M'),(3,3,'r'),(3,4,'X'),
 (2,4,'1'),(1,4,'^'),(1,3,'+'),(1,1,'>'),
 (4,4,'1'),(5,4,'v'),(5,5,'+'),(5,6,'s'),(5,7,'<'),(4,7,'^'),(4,3,'0'),(4,1,'<'),
 (3,5,'s'),(3,6,'0'),(3,7,'>'),
]
P_MAN=(2,1)
P_W,P_H=7,9

def block(p,ox,oy,w,h,cells,man):
    p.room(ox,oy,w,h)
    for (x,y,ch) in cells:
        k=(ox+x,oy+y)
        assert p.cells.get(k) in (None,ch), f'collision {k}: {p.cells.get(k)} vs {ch}'
        p.put(ox+x,oy+y,ch)
    p.man(ox+man[0],oy+man[1])

def build(save):
    p=lm.Program()
    block(p,0,0,M_W,M_H,M_CELLS,M_MAN)           # M: cols0-11 rows0-11
    block(p,0,14,C_W,C_H,C_CELLS,C_MAN)          # C: cols0-11 rows14-19
    p.pipe([(9,13),(9,12)])                      # C->M straight
    block(p,13,0,P_W,P_H,P_CELLS,P_MAN)          # P: cols13-19 rows0-8
    p.put(12,10,'>'); p.put(13,10,'-'); p.put(14,10,'^'); p.put(14,9,'^')  # M->P
    p.output_room(16,11)                         # O: cols16-18 rows11-13
    p.pipe([(17,9),(17,10)])                     # P->O
    p.input_room(14,14)                          # I: cols14-16 rows14-16
    p.pipe([(13,15),(12,15)])                    # I->C
    print('footprint',p.footprint())
    p.save(save)
if __name__=='__main__':
    build(sys.argv[1] if len(sys.argv)>1 else '/tmp/p3.man')
