import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0,_REPO + '/tools')
import littleman as lm

# TIGHT vertical C: compute mag arithmetically (M5W}), 2-branch sign, send up-leg = return.
# Narrow (~6 wide) tall loop. Returns are the send up-legs (no wasted glide).
def blockCT(p, ox, oy):
    W_,H_=7,13
    p.room(ox,oy,W_,H_)
    def P(x,y,c):
        k=(ox+x,oy+y); assert k not in p.cells or p.cells[k]==c, f'coll {(x,y)} {p.cells.get(k)}->{c}'
        p.put(ox+x,oy+y,c)
    # @ start feeds retry (4,1)=v ; returns arrive at (4,1)
    P(3,1,'@'); P(4,1,'v')          # retry
    # compute DOWN col4
    P(4,2,'r');P(4,3,'b');P(4,4,'M');P(4,5,'5');P(4,6,'W');P(4,7,'}');P(4,8,'x')  # x[bit0]
    # x(4,8)S: bit0=0(open'()->CCW->E->(5,8); bit0=1->CW->W->(3,8)
    # '(' open: send up col5
    P(5,8,'^');P(5,7,'s');P(5,6,'r');P(5,5,'s')  # up-leg send
    P(5,4,'|') if False else None
    P(5,1,'<')                      # top of col5 -> W -> retry(4,1)
    # glide (5,4)(5,3)(5,2) are blank (nop, man heads N)
    # bit0=1 subtree
    P(3,8,']');P(2,8,'x')           # (3,8)] BP>>1 ; (2,8)x[bit1]
    # x(2,8)W: bit1=1(open[{)->CW->N->(2,7); bit1=0(close)->CCW->S->(2,9)
    # open[{ : send up col2
    P(2,7,'s');P(2,6,'r');P(2,5,'s')
    P(2,1,'>')                      # top col2 -> E -> (3,1)@ -> (4,1) retry
    # close : negate then send up col1
    P(2,9,'N');P(2,10,'<');P(1,10,'^');P(1,9,'s');P(1,8,'r');P(1,7,'s')
    P(1,1,'>')                      # top col1 -> E -> (2,1)> -> ...
    p.man(ox+3,oy+1)
    return (ox,oy,W_,H_)

# standalone test I->C->O
p=lm.Program()
blockCT(p,0,5)
p.input_room(0,0); p.output_room(0,20)
p.pipe([(1,3),(1,4)]); p.pipe([(1,18),(1,19)])
p.save('/tmp/ct.man')
print(p.render())
