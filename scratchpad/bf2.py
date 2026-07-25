import sys; sys.path.insert(0,'tools'); sys.path.insert(0,'scratchpad')
from rb import B, Man
b=B(); p=b.p; C=b.C; mpath=b.mpath

WIDTH=40; HEIGHT=70; RCH=WIDTH-3    # right channel column (kept clear)
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

# ---- line(y, ops): man enters (1,y) heading E via feeder '>', executes ops
#      [(col,ch),...] in ascending col order, exits at (lastcol+1, y) heading E.
def line(y, ops):
    C(1,y,'>'); mm=Man(b,2,y)
    for col,ch in ops: mm.at(col,ch)
    return mm
def down(fromx,fromy,ty):
    """straight down at fromx to row ty-1, west to col1, down into feeder (1,ty)."""
    mpath([(fromx,fromy),(fromx,ty-1),(1,ty-1),(1,ty)])
def up_right(fromx,fromy,ty):
    """down 1, east to RCH, up to ty-1, west to col1, down into feeder(1,ty)."""
    mpath([(fromx,fromy),(fromx,fromy+1),(RCH,fromy+1),(RCH,ty-1),(1,ty-1),(1,ty)])

# ================= PREAMBLE (rows 1-4) =================
C(1,1,'@'); m=Man(b,2,1)
m.at(cIN,'r')
m.at(9,'`').op('1').op('6').op('`').op('b')    # A=16,BP=16
mpath([(m.x,1),(m.x,2),(1,2),(1,3)])
C(1,3,'>'); ms=Man(b,2,3)
ms.at(5,'0').at(cDF,'s').at(10,'m').at(11,'d')
mpath([(11,4),(1,4),(1,3)])                    # loopback
mx=Man(b,12,3); mx.at(cWF,'s').at(cFF,'s')
down(mx.x,3,6)

# ================= PHASE A (rows 6-12) =================
AY=6
m=line(AY,[(cIN,'r')]); m.op('M')              # r6: A=seq;B=seq  (M at col5)
m.op(' ') if False else None
down(m.x,AY,8)
m=line(8,[(cWR,'r'),(cWF,'s')])                # r8: read waiting, re-enqueue
m.op('-').op('N')                              # off = seq-waiting  (cols after 15)
m.at(cSF,'s')                                  # park off [SCR=off]
down(m.x,8,10)
m=line(10,[])                                  # r10: compute off>>4
m.op('M').op('4').op('W').op('}')              # A=off>>4  (cols 2-5)
bx,by=m.x,m.y
C(bx,by,'v'); C(bx,by+1,'X')                   # X heading S: A>0->CW(W)abort ; A==0->S continue
# ABORT
ABY=14
mpath([(bx-1,by+1),(1,by+1),(1,ABY-1),(1,ABY)]); C(1,ABY,'>')
mab=Man(b,2,ABY); mab.at(5,'1').op('N')
mpath([(mab.x,ABY),(mab.x,ABY+1),(2,ABY+1)]); C(2,ABY+1,'s'); C(1,ABY+1,'H')
# CONTINUE -> phase B
BY=18
mpath([(bx,by+2),(bx,BY-1),(1,BY-1),(1,BY)]); C(1,BY,'>')

# ================= PHASE B: fmask set + insert (rows 18-45) =================
# b1 set fmask bit [SCR=off]
m=Man(b,2,BY)
m.at(cSR,'r').at(cSF,'s')                       # A=off ; re-enqueue off
down(m.x,BY,20)
m=line(20,[]); m.op('M').op('1').op('{').op('M')  # B=off;A=1;A=1<<off=bit;B=bit
m.at(cFR,'r').op('|').at(cFF,'s')               # A=fmask|bit ; write F
down(m.x,20,22)
# b2 read val + park
m=line(22,[(cIN,'r'),(cSF,'s')])                # A=val ; park val [SCR=off,val]
down(m.x,22,24)
# b3 loop1 setup
m=line(24,[(cSR,'r'),(cSF,'s')])                # A=off ; re-enqueue off [SCR=val,off]
m.op('b')                                       # BP=off
down(m.x,24,26)
m=line(26,[(cSR,'r')]); m.op('M')               # A=val [SCR=off] ; B=val
down(m.x,26,28)
# loop1 rotate off times : feeder 28, body 29, loopback 30
L1=28
C(1,L1,'>'); C(2,L1,'d')                        # BP>0->CW(S)body ; BP==0->E exit
C(2,L1+1,'>'); mb=Man(b,3,L1+1); mb.at(cDR,'r').at(cDF,'s').op('m')
mpath([(mb.x,L1+1),(mb.x,L1+2),(1,L1+2),(1,L1)])
# exit at (3,L1) heading E:
# b5 REPLACE
mpath([(3,L1),(3,L1),(3,L1)])  # noop marker
mr=Man(b,3,L1)
mr.at(cDR,'r').op('W').at(cDF,'s')              # discard ph ; enqueue val
down(mr.x,L1,32)
# b6 loop2 setup R=15-off
m=line(32,[(cSR,'r')])                          # A=off [SCR=]
m.op('M').op('`').op('1').op('5').op('`').op('~').op('b')  # B=off;A=15;A=15^off;BP=R
down(m.x,32,34)
L2=34
C(1,L2,'>'); C(2,L2,'d'); C(2,L2+1,'>')
mb2=Man(b,3,L2+1); mb2.at(cDR,'r').at(cDF,'s').op('m')
mpath([(mb2.x,L2+1),(mb2.x,L2+2),(1,L2+2),(1,L2)])
# exit at (3,L2) -> phase C
mc=Man(b,3,L2)
mc.at(cFR,'r')                                  # A=fmask
down(mc.x,L2,38)

# ================= PHASE C: drain (rows 38-60) =================
DL=38
C(1,DL,'>'); C(2,DL,'b'); C(3,DL,'x')           # BP=fmask ; bit1->CW(S)drain ; bit0->CCW(N)stop
# STOP (N from (3,DL)) : write F, loopback to A
mpath([(3,DL-1),(3,DL-2),(RCH,DL-2)])           # up then east to RCH (row DL-2 clear)
# drain BODY (S from (3,DL))
C(3,DL+1,'>'); md=Man(b,4,DL+1)
md.at(cSF,'s')                                  # park fmask [SCR=fmask]
down(md.x,DL+1,41)
md=line(41,[(cDR,'r'),(cOUT+1,'s')])            # A=frontval ; output
down(md.x,41,43)
md=line(43,[]); md.op('0').at(cDF,'s')          # A=0 ; enqueue placeholder
down(md.x,43,45)
md=line(45,[(cWR,'r')]); md.op('M').op('1').op('+').at(cWF,'s')  # waiting++ ; write W
down(md.x,45,47)
md=line(47,[(cSR,'r')]); md.op('M').op('1').op('W').op('}')      # A=fmask>>1
up_right(md.x,47,DL)                            # loopback to drain feeder
# STOP handler feeder (below) : write F, loop to A
STOP=52
mpath([(RCH,DL-2),(RCH,STOP-1),(1,STOP-1),(1,STOP)]); C(1,STOP,'>')
msf=Man(b,2,STOP); msf.at(cFF,'s')              # write fmask to F
up_right(msf.x,STOP,AY)

open('solutions/tcp/tcp-ring.man','w').write(p.render()+"\n")
print("footprint", p.footprint())
