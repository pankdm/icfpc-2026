import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0,_REPO + '/tools')
sys.path.insert(0,_REPO + "/solutions/brackets")
import littleman as lm
from stack3_build import blockR, blockM

def blockC_cheap(p, ox, oy):
    W_,H_=17,8
    p.room(ox,oy,W_,H_)
    def P(x,y,c): p.put(ox+x,oy+y,c)
    def T(x,y,s):
        for i,ch in enumerate(s): P(x+i,y,ch)
    # main compute row2: A=char; BP=char(save); mag=char>>5
    T(1,2,'@>rbM5W}x')  # (1)@ (2)>entry (3)r (4)b (5)M (6)5 (7)W (8)}=mag (9)x[bit0]
    # x(9,2)E: bit0=0(open'()->CCW->N->(9,1); bit0=1->CW->S->(9,3)
    P(9,1,'>')          # '(' leaf heading N -> E
    # collector col11 flows S, bottom (11,5) turns E to send
    P(11,1,'v');P(11,2,'v');P(11,3,'v');P(11,4,'v');P(11,5,'>')
    # send lane row5
    T(12,5,'srs')
    # bit0=1 subtree
    P(9,3,']');P(9,4,'x')       # ] BP>>1 ; x[bit1]
    # x(9,4)S: bit1=1(open [{)->CW->W->(8,4); bit1=0(close)->CCW->E->(10,4)
    P(8,4,'v');P(8,5,'>')       # open[{ : down then E to merge (11,5)
    P(10,4,'N')                 # close: negate -> E -> (11,4)
    # return corridor from (14,5)s
    P(15,5,'v');
    for x in range(2,16): P(x,6,'<')
    P(2,6,'^')                  # up col2 to entry
    p.man(ox+1,oy+2)
    return (ox,oy,W_,H_)

def build(save):
    p=lm.Program()
    blockR(p,0,0)
    blockC_cheap(p,0,8)
    blockM(p,0,18)
    p.input_room(21,1)
    p.output_room(27,29)
    p.pipe([(20,2),(19,2)])
    p.pipe([(1,6),(1,7)])
    p.pipe([(1,16),(1,17)])
    p.pipe([(25,31),(26,31)])
    p.save(save); print('footprint',p.footprint())

if __name__=='__main__':
    build(sys.argv[1] if len(sys.argv)>1 else '/tmp/s4.man')
