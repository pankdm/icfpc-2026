# Increment 1: geometry + preamble that seeds DATA(16 zeros), W(0), F(0);
# then a stub main that echoes val (read seq discard, read val, output, loop).
# Goal: confirm it LOADS, seeds without error, and echoes case0 correctly.
import sys; sys.path.insert(0,'tools')
import littleman as lm
p = lm.Program()
placed={}
def C(x,y,ch):
    if (x,y) in placed and placed[(x,y)]!=ch and not (placed[(x,y)] in '+-|' ):
        raise SystemExit(f"COLLISION {(x,y)} {placed[(x,y)]!r} vs {ch!r}")
    placed[(x,y)]=ch; p.put(x,y,ch)
ARROW={"E":">","W":"<","N":"^","S":"v"}
def mpath(pts):
    for i in range(len(pts)-1):
        (x0,y0),(x1,y1)=pts[i],pts[i+1]
        dx=(x1>x0)-(x1<x0); dy=(y1>y0)-(y1<y0)
        d='E' if dx>0 else 'W' if dx<0 else 'S' if dy>0 else 'N'
        C(x0,y0,ARROW[d])

# CTRL room at (0,0), top wall y=0, interior y>=1
WIDTH=34; HEIGHT=16
p.room(0,0,WIDTH,HEIGHT)
# attach columns
cOUT=1; cIN=4
cDF,cDR=7,8      # DATA feed/ret
cWF,cWR=14,15    # W
cFF,cFR=21,22    # F
cSF,cSR=28,29    # SCRATCH
# IN/OUT rooms above
p.input_room(cIN-1,-5); p.pipe([(cIN,-2),(cIN,-1)])
p.output_room(cOUT-1,-5); p.pipe([(cOUT,-1),(cOUT,-2)])
def relay_above(fc,rc,RY):
    rx=fc-1
    p.room(rx,RY,6,4)
    C(rx+1,RY+1,'@'); C(rx+2,RY+1,'>'); C(rx+3,RY+1,'R'); C(rx+4,RY+1,'v')
    C(rx+2,RY+2,'^'); C(rx+3,RY+2,'s'); C(rx+4,RY+2,'<')
    p.pipe([(fc,-1),(fc,RY+4)])
    p.pipe([(rc,RY+4),(rc,-1)])
relay_above(cDF,cDR,-12)
relay_above(cWF,cWR,-8)
relay_above(cFF,cFR,-8)   # but overlaps W relay x-range? W rx=13..18, F rx=20..25 ok
relay_above(cSF,cSR,-8)
print(p.render())
print("footprint", p.footprint())

# --- round-trip test: send 5 into DATA, read back, output ---
C(1,1,'@'); C(cIN,1,'r')                 # read n discard
C(5,1,'5')                               # A=5
C(cDF,1,'s')                             # send 5 to DATA feed (col7)
C(cDR,1,'r')                             # read back from DATA ret (col8) -- blocks till circulated
# route to OUT: down then west to col2 's'
mpath([(cDR,1),(cDR,2),(2,2)]); C(2,2,'s')  # send to OUT (col1)
C(1,2,'^')  # dummy
C(1,3,'H')
mpath([(1,2),(1,3)])
open('scratchpad/t_ring_rt.man','w').write(p.render()+"\n")
