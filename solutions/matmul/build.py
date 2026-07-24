"""Matmul littleman builder — 4-ring stationary-C streaming machine.

Rings (FIFO, CTRL<->relay): SA (matrix A), SB (matrix B with block-marks),
SC (K accumulators + sentinel), H1 (holds M during seed / current-a during run).
Design + validation: see scratchpad/model.py. Tokens:
  OFFSET=1e6 (accumulators stored +OFFSET, kept positive), SC_SENT=-1,
  SA_SENT=30000, MARK=150 (t-block boundary -> fetch a), ENDMARK=250 (row done).
STATUS: seeding (S0/Seed-A/Seed-C/Seed-B) COMPLETE and verified on the oracle via
  the drain* stages; runtime (compute+output) designed but not yet wired collision-free.
  build(stage='drainA'|'drainC'|'drainB') each drain a ring to O to prove seeding.
Pipe columns on CTRL top wall (feed=out, ret=in):
  I=2 | SAfeed=5 SAret=6 | SBfeed=11 SBret=12 | SCfeed=17 SCret=18 |
  H1feed=23 H1ret=24 | O=28
Nearest-pipe is column-only (all pipes on top wall): place each r/s at a column
whose nearest incoming/outgoing is the intended pipe.
"""
import sys, os
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
import littleman as lm

OFFSET = 1000000
SA_SENT = 30000
MARK = 150
ENDMARK = 250

# pipe columns
I_=2; SAf=5; SAr=6; SBf=11; SBr=12; SCf=17; SCr=18; H1f=23; H1r=24; O_=28

class B:
    def __init__(self):
        self.p = lm.Program(); self.placed={}
    def C(self,x,y,ch):
        if (x,y) in self.placed and self.placed[(x,y)]!=ch:
            raise SystemExit(f"COLLISION {(x,y)}: {self.placed[(x,y)]!r} vs {ch!r}")
        self.placed[(x,y)]=ch; self.p.put(x,y,ch)
    def hrun(self,x,y,s):
        for i,c in enumerate(s): self.C(x+i,y,c)
    def lit(self,x,y,val):
        s='`'+str(val)+'`'; self.hrun(x,y,s); return x+len(s)  # eastward; returns next col
    def litW(self,x,y,val):
        # westward-read literal: a man walking WEST across it loads val. leftmost col=x.
        s='`'+str(val)[::-1]+'`'; self.hrun(x,y,s); return x-1  # returns col west of it

def build(stage="drainA", W=31, H=42):
    if stage in ("run","full"):
        W=40; H=74
    b=B(); C=b.C
    p=b.p
    p.room(0,0,W,H)   # CTRL: top wall y=0, interior rows 1..H-2, cols 1..W-2
    # relays above at y=RY..; straight-up pipes. Ring capacity ~= 2*(-RY-4) (feed+ret).
    # SA/SB need big capacity (N*M+1<=257, M*(K+1)<=272 values live in the ring);
    # SC needs >=K+1 but must stay SHORT-latency (re-read every MAC); H1 tiny.
    def ring(feed,ret,rx,RY):
        # relay room 6 wide at (rx,RY): interior cols rx+1..rx+4 rows RY+1,RY+2
        p.room(rx,RY,6,4)
        # relay man: @ > R v / (blank) ^ s <  -- loop returns to '>' (NOT '@')
        C(rx+1,RY+1,'@'); C(rx+2,RY+1,'>'); C(rx+3,RY+1,'R'); C(rx+4,RY+1,'v')
        C(rx+2,RY+2,'^'); C(rx+3,RY+2,'s'); C(rx+4,RY+2,'<')
        p.pipe([(feed,-1),(feed,RY+4)])   # feed CTRL->relay (up)
        p.pipe([(ret,RY+4),(ret,-1)])     # return relay->CTRL (down)
    big = -145 if stage in ("run","full") else -8   # SA/SB capacity
    scy = -24  if stage in ("run","full") else -8   # SC moderate capacity
    ring(SAf,SAr, SAf-1, big)   # SA relay cols 4..9
    ring(SBf,SBr, SBf-1, big)   # 10..15
    ring(SCf,SCr, SCf-1, scy)   # 16..21
    ring(H1f,H1r, H1f-1, -8)    # 22..27  (tiny/short)
    # I room high above at col2 (clear of relays which start col4); O at col28 (clear)
    IY=-16
    p.input_room(I_-1,IY)       # bottom wall IY+2=-14 ; center (I_, IY+1)
    p.pipe([(I_,IY+3),(I_,-1)]) # down col2: start back(up)=(I_,IY+2) I-bottom ; end fwd(down)=(I_,0) ctrl top
    p.output_room(O_-1,IY)
    p.pipe([(O_,-1),(O_,IY+3)]) # up col28 into O bottom

    # ===================== CTRL MAN CODE =====================
    # ---- S0: read N,M,K ; H1<-M ; BP=N*M ; B=K ----
    C(1,1,'@'); C(2,1,'r'); C(3,1,'M')          # A=N ; B=N
    C(4,1,'v'); C(4,2,'<'); C(1,2,'v'); C(1,3,'>')
    C(2,3,'r')                                   # A=M
    C(H1f,3,'s')                                 # H1 <- M   (col23 -> H1feed)
    C(H1f+1,3,'*'); C(H1f+2,3,'b')               # A=N*M ; BP=NM   (B still =N)
    C(H1f+3,3,'v'); C(H1f+3,4,'<'); C(1,4,'v'); C(1,5,'>')
    C(2,5,'r'); C(3,5,'M')                       # A=K ; B=K
    # route down to Seed-A racetrack entry at (2,7)'>' (3,7)'d'
    C(4,5,'v'); C(4,6,'<'); C(2,6,'v')           # to (2,7)
    # ---- Seed-A racetrack at col3 : body r(I) s(SAfeed) m ----
    C(2,7,'>'); C(3,7,'d')
    C(3,8,'r'); C(3,9,'s'); C(3,10,'m'); C(3,11,'<')
    C(2,11,'^')                                  # up col2 back to (2,7)
    # exit (BP==0): d straight east on row7
    endcol=b.lit(SAf,7,SA_SENT)                   # A=SA_SENT ; literal cols5.. ; endcol=next free
    C(endcol,7,'v'); C(endcol,8,'<')              # turn down then west on row8
    C(SAf,8,'s')                                  # s SAfeed <- SA_SENT  (col5)
    C(SAf-1,8,'v')                                # (4,8) down

    if stage in ("full","drainC","drainB","run"):
        # ---- Seed-C: SC <- [OFFSET*K, SC_SENT] ; B=K -> BP=K ----
        C(4,13,'>'); C(5,13,'W'); C(6,13,'b')     # A=K ; BP=K   (B=junk)
        b.lit(8,13,OFFSET)                         # A=OFFSET  (cols8..16)
        C(17,13,'v'); C(17,14,'<'); C(16,14,'v'); C(16,15,'>')  # route to racetrack
        C(17,15,'d')                               # racetrack entry (BP>0 -> CW south)
        C(17,16,'s'); C(17,17,'m'); C(17,18,'<'); C(16,18,'^')  # body s(SCfeed) m ; loop col16
        # exit (BP==0): d straight east -> Seed-C-done ; exit WEST at row19 to col4 then down
        C(19,15,'v'); C(19,16,'1'); C(19,17,'N'); C(19,18,'s')  # A=-1=SC_SENT -> s SCfeed(col19)
        C(19,19,'<'); C(4,19,'v')                  # west row19 to col4, then down

    if stage in ("full","drainB","run"):
        # ================= Seed-B ================= (from (4,19)v ; H1=M, B=junk)
        # INIT (row20): r H1ret->A=M ; re-enq H1feed ; BP=M
        C(4,20,'>'); C(H1r,20,'r')                 # (4,20)> east .. (24,20)r  A=M
        C(H1r+1,20,'v'); C(H1r+1,21,'<')           # (25,20)v (25,21)<
        C(H1f,21,'s'); C(H1f-1,21,'b')             # (23,21)s reenq M ; (22,21)b BP=M
        C(21,21,'v'); C(21,25,'<')                 # down col21 to (21,25)< into LOOP
        # LOOP (row25, westbound): r SCret ; re-enq SCfeed ; N ; X
        C(20,25,'<'); C(SCr,25,'r'); C(SCf,25,'s'); C(16,25,'N'); C(15,25,'X')
        #  X west: OFFSET(-x<0) CCW south=BREAD ; SENT(-x>0) CW north=MARKINS
        # BREAD (south): r I@3 ; s SBfeed@11 ; loop up col20 to merge
        C(15,26,'<'); C(3,26,'r'); C(2,26,'v'); C(2,27,'>')
        C(SBf,27,'s'); C(20,27,'^')
        # MARKINS (north): m ; d
        C(15,24,'m'); C(15,23,'d')                 # BP>0 CW north->east=MARK ; BP==0 straight north=ENDMARK
        # MARK (d CW -> east at 16,23): east->col22, down col22 to row32, WEST load MARK, s SBfeed, loop
        C(16,23,'>'); C(22,23,'v'); C(22,32,'<')   # to row32 heading west
        w=b.litW(13,32,MARK)                       # cols13..17 ; man exits at col12 heading west (A=MARK)
        C(SBf,32,'s')                              # (11,32) s SBfeed (man heading west, col11)
        C(10,32,'v'); C(10,33,'>'); C(20,33,'^')   # loop back: down,east,up col20 to merge(20,25)
        # ENDMARK (d straight north -> 15,22): east->col27, down to row36, WEST load ENDMARK, s SBfeed
        C(15,22,'>'); C(27,22,'v'); C(27,36,'<')   # to row36 heading west
        b.litW(13,36,ENDMARK)                      # cols13..17 ; exits col12 heading west (A=ENDMARK)
        C(SBf,36,'s')                              # (11,36) s SBfeed
        C(10,36,'v'); C(10,37,'>')                 # -> SEEDDONE lane row37
        if stage=="drainB":
            # SB now = [b.., MARK, .., ENDMARK]. drain SB->O to inspect (loop forever).
            C(12,37,'r'); C(O_,37,'s')             # (10,37)> east: r SBret@12 ; s O@28
            C(O_+1,37,'v'); C(O_+1,38,'<'); C(11,38,'^'); C(11,37,'>')  # loop
            return b
        # ===================== RUNTIME =====================
        # Flowchart (validated in model.py): FETCHA / MAIN-classify / MAC / MARKVE /
        # MARKH / ENDH / OUTLOOP. Two vertical highways: col3 (converge->FETCHA),
        # col34 (converge->MAIN). Column discipline picks pipes (all attach y=-1).
        # Tokens: SA_SENT=30000, MARK=150, ENDMARK=250, OFFSET=1e6, SC_SENT=-1.

        # ---- START: man at (11,37) heading east -> route to FETCHA entry (3,42) ----
        C(11,37,'v'); C(11,41,'<'); C(3,41,'v')     # down col11, west row41, down col3

        # ---- FETCHA (row42, eastward, entry (3,42)) ----
        #   r SA -> A=a ; M B=a ; s H1f (store a) ; r H1r (discard old, A=old,B=a)
        #   500 ; - (A=500-a) ; X: A>0 real->S ; A<0 SENT->N (halt)
        C(3,42,'>')
        C(SAr,42,'r'); C(SAr+1,42,'M')              # (6)r SA->A=a ; (7)M B=a
        C(H1f,42,'s'); C(H1r,42,'r')                # (23)s store a ; (24)r discard old
        b.lit(25,42,500); C(30,42,'-'); C(31,42,'X')# A=500 ; A=500-a ; branch
        C(31,41,'H')                                # SENT (north) -> halt
        C(31,43,'>'); C(34,43,'v')                  # real (south) -> east to col34 -> down

        # ---- MAIN read (row48, westward, entry (34,48)) ----
        #   r SB -> A=x ; s SB reenq ; M B=x ; then classify
        C(34,48,'<')
        C(SBr,48,'r'); C(SBf,48,'s'); C(10,48,'M'); C(9,48,'v')
        # ---- MAIN classify (row50 eastward -> X row51) ----
        #   100 ; N (A=-100) ; + (A=x-100, B=x) ; X south: A<0 real->E ; A>0 mark->W
        C(9,50,'>'); b.lit(10,50,100); C(15,50,'N'); C(16,50,'+'); C(17,50,'v')
        C(17,51,'X')
        # real -> East: glide to col28, down to MAC entry (28,54)
        C(28,51,'v'); C(28,54,'<')
        # ---- MAC (row54, westward) ----
        #   r H1r A=a ; s H1f reenq ; * A=a*b ; M B=a*b ; r SCr A=c ; + ; s SCf store
        C(H1r,54,'r'); C(H1f,54,'s'); C(22,54,'*'); C(21,54,'M')
        C(SCr,54,'r'); C(SCf,54,'+'); C(16,54,'s')
        # MAC return -> MAIN via col34
        C(15,54,'v'); C(15,55,'>'); C(34,55,'^')

        # mark -> West: glide to col13, down to MARKVE row58
        C(13,51,'v'); C(13,58,'<')
        # ---- MARKVE (row58 westward -> X row57 north) ----
        #   200 ; - (A=200-x, B=x) ; ^ ; X north: A>0 MARK->E ; A<0 ENDMARK->W
        b.litW(8,58,200); C(7,58,'-'); C(6,58,'^'); C(6,57,'X')
        # MARK -> East: glide row57 to col22, down to MARKH row60
        C(22,57,'v'); C(22,60,'<')
        # ---- MARKH (row60 westward): r SCr (pop SENT) ; s SCf (reenq) -> FETCHA ----
        C(SCr,60,'r'); C(SCf,60,'s'); C(3,60,'^')
        # ENDMARK -> West: (5,57) -> down col4 -> east row64 -> down col23 -> ENDH row65
        C(5,57,'<'); C(4,57,'v'); C(4,64,'>'); C(23,64,'v'); C(23,65,'<')
        # ---- ENDH (row65 westward): r SCr (pop leading SENT) ; s SCf (reenq) -> OUTLOOP
        C(SCr,65,'r'); C(SCf,65,'s'); C(16,65,'v'); C(16,67,'>')
        # ---- OUTLOOP read (row67 eastward): r SCr A=v ; X east: A>0 emit->S ; A<0 done->N
        C(SCr,67,'r'); C(19,67,'X')
        # emit (south) -> compute real c, emit, reset OFFSET, loop
        C(19,68,'>'); C(20,68,'M'); b.lit(21,68,OFFSET); C(30,68,'W'); C(31,68,'-')
        C(32,68,'v'); C(32,69,'<'); C(O_,69,'s'); C(27,69,'W'); C(SCf,69,'s'); C(16,69,'^')
        # done (north) -> reenq SENT -> FETCHA
        C(19,66,'<'); C(SCf,66,'s'); C(3,66,'^')
        return b

    if stage=="drainC":
            C(4,21,'>')                            # entry (loop-back target)
            C(18,21,'r')                           # A=c (SCret@18)
            C(19,21,'X')                           # c>0 acc CW south ; c<0 SENT CCW north
            C(19,22,'>'); C(O_,22,'s')             # acc: south then east to O
            C(O_+1,22,'v'); C(O_+1,23,'<'); C(4,23,'^')  # loop back up col4
            C(19,20,'H')                           # SENT north -> H
            return b

    if stage=="drainA":
        # DRAIN SA to O : loop r(SAret@6) ; A=500-v ; X: real>0 CW(south) SENT<0 CCW(north)
        C(4,9,'>')                                # entry / loop-back target
        C(SAr,9,'r'); C(SAr+1,9,'M')              # A=v ; B=v
        c=b.lit(9,9,500)                          # A=500 ; ends col c-1
        C(c,9,'-')                                # A=500-v  (B=v)
        C(c+1,9,'X')                              # real>0 CW south ; SENT<0 CCW north
        # real: south then east to s O then loop back up col4
        C(c+1,10,'>')                             # heading south hit here -> turn east
        C(O_,10,'s')                              # s O
        C(O_+1,10,'v'); C(O_+1,11,'<'); C(4,11,'^')  # loop back up col4 -> (4,9)
        # SENT: north -> H
        C(c+1,8,'H')
    return b

if __name__=="__main__":
    import sys
    stage = sys.argv[1] if len(sys.argv)>1 else "run"
    b=build(stage=stage)
    out = b.p.render()+"\n"
    if stage in ("run","full"):
        open(os.path.join(os.path.dirname(__file__),"matmul-run.man"),"w").write(out)
    print(out)
    print("footprint",b.p.footprint())
