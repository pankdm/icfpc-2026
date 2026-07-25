import sys; sys.path.insert(0,'tools'); sys.path.insert(0,'scratchpad')
from rb import B, Man
b=B(); p=b.p; C=b.C; mpath=b.mpath
WIDTH=36; HEIGHT=30
p.room(0,0,WIDTH,HEIGHT)
cOUT=1; cIN=4
cDF,cDR=7,8; cWF,cWR=14,15; cFF,cFR=21,22; cSF,cSR=28,29
p.input_room(cIN-1,-5); p.pipe([(cIN,-2),(cIN,-1)])
p.output_room(cOUT-1,-5); p.pipe([(cOUT,-1),(cOUT,-2)])
def relay(fc,rc,RY):
    rx=fc-1; p.room(rx,RY,6,4)
    C(rx+1,RY+1,'@'); C(rx+2,RY+1,'>'); C(rx+3,RY+1,'R'); C(rx+4,RY+1,'v')
    C(rx+2,RY+2,'^'); C(rx+3,RY+2,'s'); C(rx+4,RY+2,'<')
    p.pipe([(fc,-1),(fc,RY+4)]); p.pipe([(rc,RY+4),(rc,-1)])
relay(cDF,cDR,-12); relay(cWF,cWR,-8); relay(cFF,cFR,-8); relay(cSF,cSR,-8)

def feeder(y):
    C(1,y,'>'); return Man(b,2,y)

# ===== PREAMBLE =====
C(1,1,'@'); m=Man(b,2,1)
m.at(cIN,'r')                          # read n (discard)
m.at(9,'`').op('1').op('6').op('`').op('b')   # A=16, BP=16
# down to DATA-seed loop feeder row3
mpath([(m.x,m.y),(m.x,3),(1,3)])
C(1,3,'>'); ms=Man(b,2,3)
ms.at(5,'0'); ms.at(cDF,'s'); ms.at(10,'m'); ms.at(11,'d')  # 0,send,BP--,d-branch
# CW(S) loop back to feeder(1,3); straight-E exits at col12
mpath([(11,4),(1,4),(1,3)])
mx=Man(b,12,3)
mx.at(cWF,'s'); mx.at(cFF,'s')          # seed W=0, F=0 (A=0)
mpath([(mx.x,mx.y),(mx.x,5),(1,5),(1,6)])  # go to MAIN feeder row6

# ===== PHASE A ===== feeder row6
AY=6
ma=feeder(AY)
ma.at(cIN,'r').op('M')                  # A=seq ; B=seq
ma.at(cWR,'r')                          # A=waiting
ma.at(cWF,'s')                          # re-enqueue waiting (auto newrow) ; A=waiting
ma.op('-').op('N')                      # A = waiting-seq = -off ; N -> off
ma.at(cSF,'s')                          # park off in SCRATCH ; A=off
ma.op('M').op('4').op('W').op('}')      # B=off;A=4;swap->A=off,B=4;A=off>>4
# branch heading S into X at (bx,by)
bx,by=ma.x,ma.y
C(bx,by,'v'); C(bx,by+1,'X')            # turn S then X
# X heading S: A>0 -> CW -> W (ABORT) ; A==0 -> straight S (CONTINUE)
# ABORT: route W to abort feeder
mpath([(bx-1,by+1),(1,by+1),(1,by+2)])  # W then down to abort feeder? use dedicated
# CONTINUE: straight S -> route to continue feeder
mpath([(bx,by+2),(bx,by+3),(1,by+3)])   # temp
# --- ABORT lane: output -1, halt ---
# put abort feeder at row by+1 leftside is used; place abort code at a clear row
ABY=by+5
C(1,ABY,'>'); mab=Man(b,2,ABY)
mab.at(5,'1').op('N')                   # A=-1
mab.at(3+0, 's') if False else None
# send -1 to OUT: need s near col2. newrow then at col2.
mab.at(cOUT+1,'s')                      # s at col2 -> OUT(col1)
mab.op('H')
# wire ABORT branch (from bx-1,by+1 heading W) to abort feeder(1,ABY)
mpath([(1,by+1),(1,ABY)])
# --- CONTINUE feeder ---
CY=by+3
C(1,CY,'>'); mc=Man(b,2,CY)
# STUB: read val (discard), loop back to PHASE A feeder(1,AY)
mc.at(cIN,'r')
mpath([(mc.x,mc.y),(mc.x,mc.y+1),(1,mc.y+1),(1,AY)])   # loop back to phase A

open('scratchpad/rb1.man','w').write(p.render()+"\n")
print(p.render())
print("footprint", p.footprint())
