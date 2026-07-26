import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0,_REPO + '/tools')
import littleman as lm

BIAS=10001
p=lm.Program(); placed={}
def C(x,y,ch):
    if (x,y) in placed and placed[(x,y)]!=ch:
        raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]!r} vs {ch!r}")
    placed[(x,y)]=ch; p.put(x,y,ch)
def HR(x,y,s):   # east run
    for i,c in enumerate(s): C(x+i,y,c)

# rooms
p.room(0,5,18,30)
p.input_room(6,0); p.pipe([(7,3),(7,4)])
p.room(30,6,6,6)
p.pipe([(18,8),(29,8)])       # ring-send P->R
p.pipe([(29,9),(18,9)])       # ring-recv R->P
p.man(31,8)
for (x,y,c) in [(32,8,'>'),(33,8,'r'),(34,8,'v'),(32,9,'^'),(33,9,'s'),(34,9,'<')]: C(x,y,c)
p.output_room(2,37); p.pipe([(3,35),(3,36)])

# READ + MARKER
C(1,6,'@'); C(2,6,'>'); C(3,6,'v')
C(3,7,'r'); C(3,8,'b'); C(3,9,'v'); C(3,10,'a')
# VALUE (E)
HR(4,10,'rM')
HR(6,10,'`10001`')     # 6..12
C(13,10,'+'); C(14,10,'s'); C(15,10,'^')
C(15,9,'<'); C(14,9,'m')            # (13..4,9) spaces to (3,9)
# MARKER (S)
C(3,11,'1'); C(3,12,'N'); C(3,13,'>')   # (4..12,13) spaces
C(13,13,'s'); C(14,13,'H')

print(p.render()); print('footprint',p.footprint())
p.save(_REPO + '/scratchpad/sort1.man')
