import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0,_REPO + '/tools')
import littleman as lm
def blockMT(p, ox, oy):
    W_,H_=12,21
    p.room(ox,oy,W_,H_)
    def P(x,y,c):
        k=(ox+x,oy+y); assert k not in p.cells or p.cells.get(k)==c, f'coll {(x,y)} {p.cells.get(k)}->{c}'
        p.put(ox+x,oy+y,c)
    # INIT: @ 1 M (A=1,B=1=S) -> retry col4
    P(1,1,'@');P(2,1,'1');P(3,1,'M');P(4,1,'v');P(4,2,'v')   # @1M ; retry(4,2)
    # retry(4,2) face S ; r ; X
    P(4,3,'r');P(4,4,'X')
    # X(4,4)S: push>0->CW->W->(3,4); pop<0->CCW->E->(5,4); end0->S->(4,5)
    # PUSH: buffer (3,4)< -> col2 down
    P(3,4,'<');P(2,4,'v');P(2,5,'+');P(2,6,'+');P(2,7,'+');P(2,8,'M');P(2,9,'r')
    # push return -> col1 up -> retry
    P(2,10,'<');P(1,10,'^');P(1,2,'>');P(2,2,'>');P(3,2,'>')  # (1,2)->E->(2,2)(3,2)->retry(4,2)
    # POP: buffer (5,4)> -> col6 down
    P(5,4,'>');P(6,4,'v');P(6,5,'+');P(6,6,'M');P(6,7,'3');P(6,8,'W');P(6,9,'/')
    P(6,10,'W');P(6,11,'b');P(6,12,'d')   # test r>0
    # d(6,12)S: r>0->CW->W->(5,12) OFFENSE ; r==0->S->(6,13)
    P(6,13,'W');P(6,14,'b');P(6,15,'d')   # test q>0
    # d(6,15)S: q>0->CW->W->(5,15) MATCH ; q<=0->S->(6,16) OFFENSE2
    # MATCH (5,15): M(newS=q) then r(discard) -> return col1
    P(5,15,'M');P(4,15,'r');P(3,15,'<');P(2,15,'<');P(1,15,'^')  # up col1 to retry (shares (1,2))
    # OFFENSE testr (5,12): r s H (going W)
    P(5,12,'r');P(4,12,'s');P(3,12,'H')
    # OFFENSE2 (6,16): r s H (going S)
    P(6,16,'r');P(6,17,'s');P(6,18,'H')
    # END (4,5) down: W b m d
    P(4,5,'W');P(4,6,'b');P(4,7,'m');P(4,8,'d')
    # d(4,8)S: unclosed(BP>0)->CW->W->(3,8) ; balanced->S->(4,9)
    P(3,8,'v');P(3,9,'r');P(3,10,'s');P(3,11,'H')   # unclosed
    P(4,9,'0');P(4,10,'s');P(4,11,'H')              # balanced
    p.man(ox+1,oy+1)
    return (ox,oy,W_,H_)
p=lm.Program()
try:
    blockMT(p,0,0); print(p.render())
except AssertionError as e: print("COLL",e)
