import sys; sys.path.insert(0,'tools'); sys.path.insert(0,'scratchpad')
from rb import B, Man
b=B(); p=b.p; C=b.C; mpath=b.mpath

WIDTH=38; HEIGHT=64; RIGHT=WIDTH-4   # right vertical channel col
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

def feeder(y): C(1,y,'>'); return Man(b,2,y)
def enter_above(fromx,fromy,ty):
    """route man at (fromx,fromy) heading E -> feeder (1,ty), entering from above."""
    mpath([(fromx,fromy),(fromx,ty-1),(1,ty-1),(1,ty)])
def loopback_right(fromx,fromy,ty):
    """route man up via RIGHT channel to feeder (1,ty) from above."""
    mpath([(fromx,fromy),(fromx,fromy+1),(RIGHT,fromy+1),(RIGHT,ty-1),(1,ty-1),(1,ty)])

# counter loop that rotates DATA `BP` times (r@cDR,s@cDF,m). feeder at LY.
def rot_loop(LY):
    C(1,LY,'>'); C(2,LY,'d')      # E; BP>0->CW(S) body ; BP==0->straight(E) exit
    C(2,LY+1,'>'); mb=Man(b,3,LY+1)   # body row, heading E
    mb.at(cDR,'r').at(cDF,'s').op('m')  # rotate + BP--
    ex=mb.x
    mpath([(ex,LY+1),(ex,LY+2),(1,LY+2),(1,LY)])   # loopback up col1 to feeder
    return (3,LY)   # exit cell (man heading E at col3,LY when BP==0)

# ================= PREAMBLE =================
C(1,1,'@'); m=Man(b,2,1)
m.at(cIN,'r')                                  # read n discard
m.at(9,'`').op('1').op('6').op('`').op('b')    # A=16,BP=16
mpath([(m.x,1),(m.x,2),(1,2),(1,3)])           # -> seed feeder(1,3)
C(1,3,'>'); ms=Man(b,2,3)
ms.at(5,'0').at(cDF,'s').at(10,'m').at(11,'d') # 0->A, send DATA, BP--, d
mpath([(11,4),(1,4),(1,3)])                    # loopback
mx=Man(b,12,3); mx.at(cWF,'s').at(cFF,'s')     # seed W=0,F=0
enter_above(mx.x,3,6)                          # -> phase A feeder(1,6)

# ================= PHASE A ================= feeder AY=6
AY=6
ma=feeder(AY)
ma.at(cIN,'r').op('M')                # A=seq ; B=seq
ma.at(cWR,'r').at(cWF,'s')            # A=waiting ; re-enqueue waiting
ma.op('-').op('N')                    # A=waiting-seq ; N-> off
ma.at(cSF,'s')                        # park off  [SCR=off]
ma.newrow()                           # reset columns
ma.op('M').op('4').op('W').op('}')    # A=off>>4
bx,by=ma.x,ma.y
C(bx,by,'v'); C(bx,by+1,'X')          # approach X heading S: A>0->CW(W) abort; A==0->S continue
# ABORT feeder
ABY=by+3
mpath([(bx-1,by+1),(1,by+1),(1,ABY-1),(1,ABY)]); C(1,ABY,'>')
mab=Man(b,2,ABY); mab.at(5,'1').op('N')      # A=-1
mpath([(mab.x,ABY),(mab.x,ABY+1),(2,ABY+1)]); C(2,ABY+1,'s'); C(1,ABY+1,'H')
# CONTINUE -> phase B feeder
BY=ABY+4
mpath([(bx,by+2),(bx,BY-1),(1,BY-1),(1,BY)]); C(1,BY,'>')

# ================= PHASE B (fmask set + insert) ================= feeder BY  [SCR=off]
mbb=Man(b,2,BY)
# b1: set fmask bit
mbb.at(cSR,'r').at(cSF,'s')           # A=off ; re-enqueue off [SCR=off]
mbb.newrow()
mbb.op('M').op('1').op('{')           # B=off;A=1;A=1<<off=bit
mbb.op('M')                           # B=bit
mbb.at(cFR,'r').op('|').at(cFF,'s')   # A=fmask;A|bit;write F
# b2: read val + park
mbb.newrow()
mbb.at(cIN,'r').at(cSF,'s')           # A=val ; park val [SCR=off,val]
# b3: loop1 setup
mbb.newrow()
mbb.at(cSR,'r').at(cSF,'s')           # A=off ; re-enqueue off [SCR=val,off]
mbb.op('b')                           # BP=off
mbb.at(cSR,'r').op('M')               # A=val [SCR=off] ; B=val
# route into loop1 feeder
L1Y=mbb.y+2
enter_above(mbb.x,mbb.y,L1Y)
ex=rot_loop(L1Y)                      # rotate off times ; exit at (3,L1Y)
# b5: REPLACE (man at exit (3,L1Y) heading E, BP=0,B=val,SCR=off)
mr=Man(b,ex[0],ex[1])
mr.at(cDR,'r').op('W').at(cDF,'s')    # A=placeholder(discard);W->A=val,B=ph;enqueue val
# b6: loop2 setup: R=15-off
mr.newrow()
mr.at(cSR,'r')                        # A=off [SCR=]
mr.op('M').op('`').op('1').op('5').op('`').op('~').op('b')  # B=off;A=15;A=15^off=R;BP=R
L2Y=mr.y+2
enter_above(mr.x,mr.y,L2Y)
ex2=rot_loop(L2Y)                     # rotate R times
# ================= PHASE C (drain) =================
mc=Man(b,ex2[0],ex2[1])
mc.at(cFR,'r')                        # A=fmask
DLY=mc.y+2
enter_above(mc.x,mc.y,DLY)
# DRAIN loop feeder DLY
C(1,DLY,'>'); C(2,DLY,'b')            # BP=fmask (A=fmask preserved)
C(3,DLY,'x')                          # low bit1->CW(S) drain ; bit0->CCW(N) stop
# STOP lane (N from (3,DLY)) -> write F, loopback to phase A
mpath([(3,DLY-1),(3,DLY-2)])         # go up a bit
# put stop code: write fmask(A) to F then loopback to A
# man heading N at (3,DLY-2); turn to reach cFF? Instead route to a stop feeder
STY=DLY-2
# route N-lane to a clear row above, then do write-F + loopback
mpath([(3,DLY-1),(3,STY),(RIGHT,STY)])   # up then east to right channel top area
# stop handler at row STY using right channel: need to write F (s@cFF=22) with A=fmask
# simpler: place stop handler BELOW everything to avoid clutter -> but need A=fmask.
# We'll route stop N-lane to a dedicated stop feeder far below via right channel down.
# --- place DRAIN body (S from (3,DLY)) ---
C(3,DLY+1,'>'); md=Man(b,4,DLY+1)     # drain body row
md.at(cSF,'s')                        # park fmask [SCR=fmask] (A=fmask)
md.newrow()
md.at(cDR,'r').at(cOUT+1,'s')         # A=frontval ; output
md.newrow()
md.op('0').at(cDF,'s')                # A=0 ; enqueue placeholder
md.newrow()
md.at(cWR,'r').op('M').op('1').op('+').at(cWF,'s')  # waiting++ ; write W
md.newrow()
md.at(cSR,'r').op('M').op('1').op('W').op('}')      # A=fmask>>1
# loopback to DL feeder (up, via right channel)
loopback_right(md.x,md.y,DLY)
# --- STOP handler: write F, loop to phase A. Reuse right channel down to a feeder ---
# route the earlier N-lane (at RIGHT,STY) down the right channel to STOPY feeder
STOPY=md.y+4
mpath([(RIGHT,STY),(RIGHT,STOPY-1),(1,STOPY-1),(1,STOPY)]); C(1,STOPY,'>')
msf=Man(b,2,STOPY)
msf.at(cFF,'s')                       # write fmask(A) to F
loopback_right(msf.x,msf.y,AY)        # loop back to phase A

open('solutions/tcp/tcp-ring.man','w').write(p.render()+"\n")
print("footprint", p.footprint())
print(p.render())
