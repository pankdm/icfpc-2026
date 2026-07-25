import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys; sys.path.insert(0,_REPO + '/tools'); sys.path.insert(0,_REPO + '/solutions/tcp')
from rb import B, Man
b=B(); p=b.p; C=b.C; mpath=b.mpath

WIDTH=42; HEIGHT=74; RCH=37; RCH2=39
p.room(0,0,WIDTH,HEIGHT)
cOUT=1; cIN=4
cDR,cDF=7,8; cWR,cWF=14,15; cFR,cFF=21,22; cSR,cSF=28,29
p.input_room(cIN-1,-5); p.pipe([(cIN,-2),(cIN,-1)])
p.output_room(cOUT-1,-5); p.pipe([(cOUT,-1),(cOUT,-2)])
def relay(rc,fc,RY):
    rx=min(rc,fc)-1; p.room(rx,RY,6,4)
    C(rx+1,RY+1,'@'); C(rx+2,RY+1,'>'); C(rx+3,RY+1,'R'); C(rx+4,RY+1,'v')
    C(rx+2,RY+2,'^'); C(rx+3,RY+2,'s'); C(rx+4,RY+2,'<')
    p.pipe([(fc,-1),(fc,RY+4)]); p.pipe([(rc,RY+4),(rc,-1)])
relay(cDR,cDF,-12); relay(cWR,cWF,-8); relay(cFR,cFF,-8); relay(cSR,cSF,-8)

def line(y, ops=()):
    C(1,y,'>'); mm=Man(b,2,y)
    for col,ch in ops: mm.at(col,ch)
    return mm
def down(fromx,fromy,ty):
    mpath([(fromx,fromy),(fromx,ty-1),(1,ty-1),(1,ty)])
def up_right(fromx,fromy,ty,chan=RCH):
    mpath([(fromx,fromy),(fromx,fromy+1),(chan,fromy+1),(chan,ty-1),(1,ty-1),(1,ty)])
def rotloop(LY, exit_row):
    C(1,LY,'>'); C(2,LY,'d'); C(2,LY+1,'>')
    mb=Man(b,3,LY+1); mb.at(cDR,'r').at(cDF,'s').op('m')
    mpath([(mb.x,LY+1),(mb.x,LY+2),(1,LY+2),(1,LY)])
    mpath([(3,LY),(4,LY),(4,exit_row-1),(1,exit_row-1),(1,exit_row)])
    C(1,exit_row,'>'); return Man(b,2,exit_row)

# PREAMBLE
C(1,1,'@'); m=Man(b,2,1)
m.at(cIN,'r'); m.at(9,'`').op('1').op('6').op('`').op('b')
mpath([(m.x,1),(m.x,2),(1,2),(1,3)])
C(1,3,'>'); ms=Man(b,2,3)
ms.at(5,'0').at(cDF,'s').at(10,'m').at(11,'d')
mpath([(11,4),(1,4),(1,3)])
mx=Man(b,12,3); mx.at(cWF,'s').at(cFF,'s')
down(mx.x,3,6)

# PHASE A
AY=6
m=line(AY,[(cIN,'r')]); m.op('M'); down(m.x,AY,8)
m=line(8,[(cWR,'r'),(cWF,'s')]); m.op('-').op('N'); m.at(cSF,'s'); down(m.x,8,10)
m=line(10); m.op('M').op('4').op('W').op('}')
bx,by=m.x,m.y; C(bx,by,'v'); C(bx,by+1,'X')
ABY=14
mpath([(bx-1,by+1),(1,by+1),(1,ABY-1),(1,ABY)]); C(1,ABY,'>')
mab=Man(b,2,ABY); mab.at(5,'1').op('N')
mpath([(mab.x,ABY),(mab.x,ABY+1),(2,ABY+1)]); C(2,ABY+1,'s'); C(1,ABY+1,'H')
BY=18
mpath([(bx,by+2),(bx,BY-1),(1,BY-1),(1,BY)]); C(1,BY,'>')

# PHASE B  [SCR=off]
m=Man(b,2,BY); m.at(cSR,'r').at(cSF,'s'); down(m.x,BY,20)
m=line(20); m.op('M').op('1').op('{').op('M'); m.at(cFR,'r').op('|'); down(m.x,20,22)
m=line(22,[(cFF,'s')]); down(m.x,22,24)
m=line(24,[(cIN,'r'),(cSF,'s')]); down(m.x,24,26)
m=line(26,[(cSR,'r'),(cSF,'s')]); m.op('b'); down(m.x,26,28)
m=line(28,[(cSR,'r')]); m.op('M'); down(m.x,28,30)
mr=rotloop(30,34)
mr.at(cDR,'r').op('W'); down(mr.x,34,36)
m=line(36,[(cDF,'s')]); down(m.x,36,38)
m=line(38,[(cSR,'r')]); m.op('M').op('`').op('1').op('5').op('`').op('~').op('b'); down(m.x,38,40)
mc=rotloop(40,44)
mc.at(cFR,'r'); down(mc.x,44,48)

# PHASE C: drain.  Branch heads SOUTH into x so both exits go sideways.
DL=48
C(1,DL,'>'); C(2,DL,'b'); C(3,DL,'v'); C(3,DL+1,'x')  # BP=fmask ; S ; x
# x heading S: low bit1 -> CW -> W (drain) ; bit0 -> CCW -> E (stop)
# DRAIN (W at (2,DL+1)) -> body feeder
mpath([(2,DL+1),(2,DL+2),(1,DL+2),(1,DL+3)]); DB=DL+3
C(1,DB,'>'); md=Man(b,2,DB); md.at(cSF,'s'); down(md.x,DB,DB+2)   # park fmask
md=line(DB+2,[(cDR,'r')]); down(md.x,DB+2,DB+4)                    # A=frontval
md=line(DB+4,[(cOUT+1,'s')]); down(md.x,DB+4,DB+6)                 # output
md=line(DB+6); md.op('0').at(cDF,'s'); down(md.x,DB+6,DB+8)        # placeholder
md=line(DB+8,[(cWR,'r')]); down(md.x,DB+8,DB+10)                   # A=waiting
md=line(DB+10); md.op('M').op('1').op('+').at(cWF,'s'); down(md.x,DB+10,DB+12)  # waiting++
md=line(DB+12,[(cSR,'r')]); md.op('M').op('1').op('W').op('}')     # A=fmask>>1
up_right(md.x,DB+12,DL,RCH)                                        # loop to DL feeder (RCH)
# STOP (E at (4,DL+1)): write F inline, then loop up to A via RCH2
C(cFF,DL+1,'s')                                                   # write F (A=fmask), man glides E
mpath([(cFF+1,DL+1),(RCH2,DL+1),(RCH2,AY-1),(1,AY-1),(1,AY)])     # up to phase A via RCH2

open(_REPO + '/solutions/tcp/tcp-ring.man','w').write(p.render()+"\n")
print("footprint", p.footprint())
