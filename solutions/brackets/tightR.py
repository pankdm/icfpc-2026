import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0,_REPO + '/tools')
import littleman as lm
def blockRT(p, ox, oy):
    W_,H_=8,11
    p.room(ox,oy,W_,H_)
    def P(x,y,c):
        k=(ox+x,oy+y); assert k not in p.cells or p.cells.get(k)==c, f'coll {(x,y)} {p.cells.get(k)}->{c}'
        p.put(ox+x,oy+y,c)
    # INIT row1
    P(1,1,'@');P(2,1,'r');P(3,1,'b');P(4,1,'0');P(5,1,'M');P(6,1,'v')
    # route down to retry(2,2) via row2 west (shared return lane)
    P(6,2,'<')
    # retry
    P(2,2,'v')          # face S
    P(2,3,'a')          # BP>0 -> CCW -> E body ; BP0 -> S end
    # BODY down col3
    P(3,3,'v');P(3,4,'1');P(3,5,'+');P(3,6,'M');P(3,7,'r');P(3,8,'s')
    # bottom turn to up col4
    P(3,9,'>');P(4,9,'^')
    # up col4: W s M m
    P(4,8,'W');P(4,7,'s');P(4,6,'M');P(4,5,'m')
    # return up col4 to row2 then west into retry
    P(4,2,'<')          # (4,4),(4,3) glide N, (4,2) turn W
    # shared return lane row2 west: (5,2)(4,2)(3,2) -> retry(2,2)
    P(5,2,'<');P(3,2,'<')
    # END down col2 from (2,4)
    P(2,4,'0');P(2,5,'s');P(2,6,'1');P(2,7,'+');P(2,8,'s');P(2,9,'H')
    p.man(ox+1,oy+1)
    return (ox,oy,W_,H_)
p=lm.Program()
blockRT(p,0,3)
p.input_room(0,0); p.output_room(11,3)
p.pipe([(1,3),(1,4)]) if False else None
# I above -> R ; R -> O to the right
p.pipe([(1,3),(1,4)])
p.pipe([(8,5),(9,5)]) if False else None
p.pipe([(8,6),(10,6)])
p.save('/tmp/rt.man')
print(p.render())
