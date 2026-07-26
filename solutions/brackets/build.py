import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys; sys.path.insert(0,_REPO + '/tools'); import littleman as lm
def route(p, pts):
    for i in range(len(pts)-1):
        x0,y0=pts[i]; x1,y1=pts[i+1]
        dx=(x1>x0)-(x1<x0); dy=(y1>y0)-(y1<y0)
        p.put(x0,y0, lm.VEC2ARROW[(dx,dy)])
def T(p,ox,oy,x,y,s): p.text(ox+x,oy+y,s)
def P(p,ox,oy,x,y,c): p.put(ox+x,oy+y,c)
def RT(p,ox,oy,pts): route(p,[(ox+x,oy+y) for x,y in pts])

def blockR(p,ox,oy):
    p.room(ox,oy,24,6)                 # rows oy..oy+5
    T(p,ox,oy,1,1,'@rb0M'); P(p,ox,oy,6,1,'v')
    P(p,ox,oy,6,2,'>'); P(p,ox,oy,7,2,'d')          # merge, CHECK(BP>0->south)
    P(p,ox,oy,7,3,'>'); T(p,ox,oy,8,3,'1+MrsWsMm')  # body row3 (cols8..16)
    P(p,ox,oy,17,3,'v'); P(p,ox,oy,17,4,'<'); P(p,ox,oy,6,4,'^')  # loopback -> (6,2)
    T(p,ox,oy,8,2,'0s1+sH')                          # END (BP==0 east from check)
    p.man(ox+1,oy+1)
    return (ox,oy,24,6)

def blockC(p,ox,oy):
    p.room(ox,oy,36,8)             # cols ox..ox+35, rows oy..oy+7
    T(p,ox,oy,1,1,'@v'); P(p,ox,oy,2,2,'>')
    T(p,ox,oy,3,2,'rM`32`W/bWM3W&WN+*M1+M0')
    P(p,ox,oy,26,2,'>'); P(p,ox,oy,27,2,'d')
    P(p,ox,oy,27,3,'+'); P(p,ox,oy,27,4,'m'); P(p,ox,oy,27,5,'<'); P(p,ox,oy,26,5,'^')
    T(p,ox,oy,28,2,'srs'); P(p,ox,oy,31,2,'v'); P(p,ox,oy,31,3,'<'); P(p,ox,oy,2,3,'^')
    p.man(ox+1,oy+1)
    return (ox,oy,36,8)

def blockM(p,ox,oy):
    p.room(ox,oy,26,19)                       # content shifted up by 6 (rows1..17)
    T(p,ox,oy,1,8,'@1M>rX')
    T(p,ox,oy,6,9,'+'); T(p,ox,oy,6,10,'+'); T(p,ox,oy,6,11,'+'); T(p,ox,oy,6,12,'M'); T(p,ox,oy,6,13,'r')
    RT(p,ox,oy,[(6,14),(4,14),(4,8)])
    T(p,ox,oy,6,7,'N'); T(p,ox,oy,6,6,'W'); T(p,ox,oy,6,5,'-'); P(p,ox,oy,6,4,'>')
    T(p,ox,oy,7,4,'M3W/WbWM1+W'); P(p,ox,oy,18,4,'>'); P(p,ox,oy,19,4,'d')
    T(p,ox,oy,19,5,'-'); T(p,ox,oy,19,6,'m'); P(p,ox,oy,19,7,'<'); P(p,ox,oy,18,7,'^')
    P(p,ox,oy,20,4,'X')
    T(p,ox,oy,20,5,'M'); T(p,ox,oy,20,6,'r')
    RT(p,ox,oy,[(20,7),(20,17),(4,17),(4,8)])
    T(p,ox,oy,21,4,'rsH')
    T(p,ox,oy,20,3,'r'); T(p,ox,oy,20,2,'s'); T(p,ox,oy,20,1,'H')
    T(p,ox,oy,7,8,'WM1W-X')
    T(p,ox,oy,13,8,'r0sH')
    T(p,ox,oy,12,9,'r'); T(p,ox,oy,12,10,'s'); T(p,ox,oy,12,11,'H')
    p.man(ox+1,oy+8)
    return (ox,oy,26,19)

def build(save):
    p=lm.Program()
    # vertical stack: I, R, C, M, O  (left-aligned, col3 vertical pipes)
    yR=5; yC=13; yM=23; yO=44
    R=blockR(p,0,yR); C=blockC(p,0,yC); M=blockM(p,0,yM)
    p.input_room(0,0)                       # I rows0..2, bottom row2
    p.pipe([(1,3),(1,4)])                   # I -> R (R top row5)
    p.pipe([(1,yR+6),(1,yC-1)])             # R bottom (row11) -> C top (row13): [(3,11),(3,12)]
    p.pipe([(1,yC+8),(1,yM-1)])             # C bottom (row21) -> M top (row23): [(3,21),(3,22)]
    p.output_room(0,yO)                     # O rows53..55
    p.pipe([(1,yM+19),(1,yO-1)])            # M bottom (row51) -> O top (row53): [(3,51),(3,52)]
    p.save(save)
    print('footprint',p.footprint())
build(sys.argv[1] if len(sys.argv)>1 else '/tmp/all.man')
