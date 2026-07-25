import sys; sys.path.insert(0,'/Users/visenbaev/icfpc26/tools'); import littleman as lm
sys.path.insert(0,'/Users/visenbaev/icfpc26/solutions/brackets')
from dsl import route as RT_
def T(p,ox,oy,x,y,s): p.text(ox+x,oy+y,s)
def P(p,ox,oy,x,y,c): p.put(ox+x,oy+y,c)
def RT(p,ox,oy,pts): RT_(p,[(ox+x,oy+y) for x,y in pts])

def blockR(p,ox,oy):            # trimmed 24->19 wide, 6 tall
    p.room(ox,oy,19,6)
    T(p,ox,oy,1,1,'@rb0M'); P(p,ox,oy,6,1,'v')
    P(p,ox,oy,6,2,'>'); P(p,ox,oy,7,2,'d')
    P(p,ox,oy,7,3,'>'); T(p,ox,oy,8,3,'1+MrsWsMm')
    P(p,ox,oy,17,3,'v'); P(p,ox,oy,17,4,'<'); P(p,ox,oy,6,4,'^')
    T(p,ox,oy,8,2,'0s1+sH')
    p.man(ox+1,oy+1); return (ox,oy,19,6)

def blockC(p,ox,oy):            # trimmed 36->33 wide, 8->7 tall
    p.room(ox,oy,33,7)
    T(p,ox,oy,1,1,'@v'); P(p,ox,oy,2,2,'>')
    T(p,ox,oy,3,2,'rM`32`W/bWM3W&WN+*M1+M0')
    P(p,ox,oy,26,2,'>'); P(p,ox,oy,27,2,'d')
    P(p,ox,oy,27,3,'+'); P(p,ox,oy,27,4,'m'); P(p,ox,oy,27,5,'<'); P(p,ox,oy,26,5,'^')
    T(p,ox,oy,28,2,'srs'); P(p,ox,oy,31,2,'v'); P(p,ox,oy,31,3,'<'); P(p,ox,oy,2,3,'^')
    p.man(ox+1,oy+1); return (ox,oy,33,7)

def blockM(p,ox,oy):            # trimmed 26->25 wide, 17 tall (rows15,16 already gone)
    p.room(ox,oy,25,16)
    T(p,ox,oy,1,8,'@1M>rX')
    T(p,ox,oy,6,9,'+'); T(p,ox,oy,6,10,'+'); T(p,ox,oy,6,11,'+'); T(p,ox,oy,6,12,'M'); T(p,ox,oy,6,13,'r')
    RT(p,ox,oy,[(6,14),(4,14),(4,8)])
    T(p,ox,oy,6,7,'N'); T(p,ox,oy,6,6,'W'); T(p,ox,oy,6,5,'-'); P(p,ox,oy,6,4,'>')
    T(p,ox,oy,7,4,'M3W/WbWM1+W'); P(p,ox,oy,18,4,'>'); P(p,ox,oy,19,4,'d')
    T(p,ox,oy,19,5,'-'); T(p,ox,oy,19,6,'m'); P(p,ox,oy,19,7,'<'); P(p,ox,oy,18,7,'^')
    P(p,ox,oy,20,4,'X')
    T(p,ox,oy,20,5,'M'); T(p,ox,oy,20,6,'r')
    RT(p,ox,oy,[(20,7),(20,14),(4,14),(4,8)])
    T(p,ox,oy,21,4,'rsH')
    T(p,ox,oy,20,3,'r'); T(p,ox,oy,20,2,'s'); T(p,ox,oy,20,1,'H')
    T(p,ox,oy,7,8,'WM1W-X')
    T(p,ox,oy,13,8,'r0sH')
    T(p,ox,oy,12,9,'r'); T(p,ox,oy,12,10,'s'); T(p,ox,oy,12,11,'H')
    p.man(ox+1,oy+8); return (ox,oy,25,16)

def build(save):
    p=lm.Program()
    R=blockR(p,0,0)      # rows0-5 cols0-18
    C=blockC(p,0,8)      # rows8-14 cols0-32
    M=blockM(p,0,17)     # rows17-32 cols0-24 (16 tall)
    p.input_room(21,1)   # I cols21-23 rows1-3
    p.output_room(27,28) # O cols27-29 rows29-31
    p.pipe([(20,2),(19,2)])   # I -> R
    p.pipe([(1,6),(1,7)])     # R -> C
    p.pipe([(1,15),(1,16)])   # C -> M
    p.pipe([(25,30),(26,30)]) # M -> O
    p.save(save); print('footprint',p.footprint())
build(sys.argv[1] if len(sys.argv)>1 else '/tmp/s3c.man')
