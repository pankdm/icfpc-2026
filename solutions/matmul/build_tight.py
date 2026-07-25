"""Matmul littleman builder — COUNTER-DRIVEN tight-MAC machine (from scratch).  [WIP]

STATUS (handoff): algorithm PROVEN (model_tight.py 202/202).  This builder emits the full
machine (header+SeedA/B/C+FETCHA/KLOOP/POSTK/OUTLOOP) but does NOT yet load on the oracle.
Remaining blockers, in order:
  1) VERTICAL-BACKTICK-LITERAL clash: the oracle scans a '`' vertically until a non-space;
     any instruction sharing a literal's backtick COLUMN (even rows away, through blanks)
     errors "expected a digit or a space between backticks".  My multi-cell literals
     (`500`,`30000`,`1000000`) put backticks on ring-mouth columns (11,12,17,18,23,24,...)
     which carry r/s ops elsewhere -> clash.  FIX: reserve 2 vertically-clear columns per
     literal (backticks there), or keep whole backtick columns blank in the man region.
  2) then: verify tiny 2x2x2 RUNS (register/route bugs likely remain in KLOOP/POSTK/OUTLOOP).
  3) then: scale ring caps (DA/DB) for the 16^3 case (needs SA cap~273, SB~256).
  4) then: FOLD SA/SB serpentines (reuse build_opt5 folded_on) + CLUSTER hot mouths for ticks.
FALLBACK: solutions/matmul/matmul-opt5.man (185M local / 230M server, RANK 2) stays best.

Algorithm validated in model_tight.py.  Key vs opt5:
  * SB flat (no marks) -> inner K-loop driven by a BP counter (no per-MAC MARK classify).
  * a-fetch via SA tokens (a | SA_SENT); row boundary via per-row block counter Mrem.
  * a held in holder H1 across K-sweep (round-trips each MAC).  SC=[c..,SC_SENT] stationary.

Rings: SA=[a..,SENT], SB=[b..](cycled), SC; holders H1(a), HK(K), HM(M), HMR(Mrem).
Columns are VARIABLES; 'tiny' uses a spread staggered (deeper-left) straight-ring layout
that is collision-free (FSM correctness on small cases).  'run' will cluster+fold later.
"""
import sys, os
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
import littleman as lm

OFFSET=1000000; SA_SENT=30000; SC_SENT=-1

# ---- spread columns (tiny), deeper-left staggered relays ----
I_=2
SAf=5;   SAr=6
HMr=11;  HMf=12       # holders: ret<feed so eastward "r then s-reenq" walks monotonically
HKr=17;  HKf=18
HMRr=23; HMRf=24      # Mrem: adjacent (dec is a vertical gadget at col HMRr)
H1r=33;  H1f=35       # gap 34
SBr=39;  SBf=40
SCr=44;  SCf=46       # gap 45 for '+'
O_=50

E=(1,0); Wd=(-1,0); N=(0,-1); S=(0,1)
ARROW={E:'>',Wd:'<',N:'^',S:'v'}
def cw(d):  return (-d[1], d[0])
def ccw(d): return (d[1], -d[0])

class Prog:
    def __init__(s): s.p=lm.Program(); s.placed={}
    def C(s,x,y,ch):
        cur=s.placed.get((x,y))
        if cur is not None and cur!=ch: raise SystemExit(f"COLLISION {(x,y)}: {cur!r} vs {ch!r} at {(x,y)}")
        s.placed[(x,y)]=ch; s.p.put(x,y,ch)
    def lit(s,x,y,val,west=False):
        st='`'+(str(val)[::-1] if west else str(val))+'`'
        for i,c in enumerate(st): s.C(x+i,y,c)

class Cur:
    def __init__(s,P,x,y,d): s.P=P; s.x=x; s.y=y; s.d=d
    def _a(s): s.x+=s.d[0]; s.y+=s.d[1]
    def op(s,ch): s.P.C(s.x,s.y,ch); s._a(); return s
    def turn(s,d2): s.P.C(s.x,s.y,ARROW[d2]); s.d=d2; s._a(); return s
    def to_col(s,tx):
        assert s.d in (E,Wd),(s.x,s.y,s.d)
        if (tx-s.x)*s.d[0]<0: raise SystemExit(f"to_col wrong dir: at {(s.x,s.y)} d={s.d} tx={tx}")
        n=0
        while s.x!=tx:
            s._a(); n+=1
            if n>200: raise SystemExit(f"to_col overshoot from {(s.x,s.y)} tx={tx}")
        return s
    def to_row(s,ty):
        assert s.d in (N,S),(s.x,s.y,s.d)
        if (ty-s.y)*s.d[1]<0: raise SystemExit(f"to_row wrong dir: at {(s.x,s.y)} d={s.d} ty={ty}")
        n=0
        while s.y!=ty:
            s._a(); n+=1
            if n>200: raise SystemExit(f"to_row overshoot from {(s.x,s.y)} ty={ty}")
        return s
    def litE(s,val): s.P.lit(s.x,s.y,val); s.x+=len(str(val))+2; return s
    def X(s):
        s.P.C(s.x,s.y,'X'); d=s.d
        return (Cur(s.P,s.x+cw(d)[0],s.y+cw(d)[1],cw(d)),
                Cur(s.P,s.x+ccw(d)[0],s.y+ccw(d)[1],ccw(d)),
                Cur(s.P,s.x+d[0],s.y+d[1],d))
    def d_(s):
        s.P.C(s.x,s.y,'d'); d=s.d
        return (Cur(s.P,s.x+cw(d)[0],s.y+cw(d)[1],cw(d)),
                Cur(s.P,s.x+d[0],s.y+d[1],d))
    def nextlane(s):
        """from heading E at (X,Y): drop, run W to col1, drop, head E at (2,Y+2)."""
        assert s.d==E
        s.turn(S).turn(Wd).to_col(1).turn(S).turn(E); return s
    def clone(s): return Cur(s.P,s.x,s.y,s.d)

def build(stage="tiny"):
    W=54; H=66
    P=Prog(); C=P.C
    P.p.room(0,0,W,H)

    def ring(feed,ret,RY):
        rx=min(feed,ret)-1
        P.p.room(rx,RY,6,4)
        C(rx+1,RY+1,'@'); C(rx+2,RY+1,'>'); C(rx+3,RY+1,'R'); C(rx+4,RY+1,'v')
        C(rx+2,RY+2,'^'); C(rx+3,RY+2,'s'); C(rx+4,RY+2,'<')
        P.p.pipe([(feed,-1),(feed,RY+4)]); P.p.pipe([(ret,RY+4),(ret,-1)])
        for yy in range(RY+4,0):
            for cc in (feed,ret): P.placed.setdefault((cc,yy),'|')
    ring(SAf,SAr,-70); ring(HMf,HMr,-64); ring(HKf,HKr,-58); ring(HMRf,HMRr,-52)
    ring(H1f,H1r,-46); ring(SBf,SBr,-40); ring(SCf,SCr,-34)
    IY=-6
    P.p.input_room(I_-1,IY);  P.p.pipe([(I_,IY+3),(I_,-1)])
    P.p.output_room(O_-1,IY); P.p.pipe([(O_,-1),(O_,IY+3)])

    # ---- FETCHA convergence highway: bring a cursor to (1,FETY) then '>' east into lane.
    FETY=32
    C(1,FETY,'>')                       # FETCHA convergence cell; col1 otherwise blank in runtime
    def go_fetcha(c):
        assert c.x==1,(c.x,c.y,c.d)
        c.to_row(FETY)                  # glide along col1 to (1,FETY)'>' -> man heads E next

    # ================= HEADER =================
    C(1,1,'@')
    c=Cur(P,2,1,E).op('r').op('M')             # A=N ; B=N
    c.nextlane()                               # -> (2,3) E
    c.op('r'); c.to_col(HMf).op('s')           # A=M ; HM<-M
    c.op('*').op('b')                          # A=N*M ; BP=NM   (B=N)
    c.nextlane()                               # -> (2,5) E
    c.op('r'); c.to_col(HKf).op('s')           # A=K ; HK<-K
    c.nextlane()                               # -> (2,7) E ; BP=NM

    # link helper: c heading E anywhere -> (2,row) heading E, via a clear down-col then col1.
    def link(c,row,down=None):
        vc = down if down is not None else c.x+2
        c.to_col(vc).turn(S).to_row(row-1).turn(Wd).to_col(1).turn(S).to_row(row).turn(E)

    # ================= SEED-A : BP=NM ; loop r I -> s SA ; then SA_SENT =================
    C(2,7,'>'); C(3,7,'d')                     # entry ; BP>0 CW E->S
    C(3,8,'r'); C(3,9,'s'); C(3,10,'m'); C(3,11,'<'); C(2,11,'^')   # body col3, loop col2 rows8-11
    c=Cur(P,4,7,E).litE(SA_SENT)               # racetrack exit (BP=0) -> A=SA_SENT (`30000` cols4-10)
    c.turn(S).turn(Wd).to_col(SAf).op('s')     # v@(11,7); west row8 to col5; s SA<-SENT ; cursor (4,8)W
    c.to_col(1).turn(S).to_row(12).turn(E)     # glide (4,8)->(1,8) [blank under literal], down to (2,12)

    # ================= SEED-B : BP=MK ; loop r I -> s SB =================
    c.to_col(HMr).op('r').to_col(HMf).op('s').op('M')          # r HM=M ; reenq ; B=M
    c.to_col(HKr).op('r').to_col(HKf).op('s').op('*').op('b')  # r HK=K ; reenq ; A=MK ; BP=MK
    link(c,14,down=c.x+1)                                       # -> (2,14) E
    C(2,14,'>'); C(3,14,'d')                                   # racetrack entry ; BP>0 CW E->S
    C(3,15,'r')                                                # body: r I -> A=b
    bl=Cur(P,4,15,E).to_col(SBf).op('s').op('m')               # s SB ; m
    bl.turn(S).turn(Wd).to_col(2).turn(N).to_row(14)           # loop up col2 -> (2,14)'>'
    c=Cur(P,4,14,E)                                            # racetrack exit (BP=0)

    # ================= SEED-C : BP=K ; loop OFFSET->SC ; SC_SENT ; HMR<-M =================
    link(c,18,down=15)                                         # -> (2,18) E (down col15, clear of body)
    c.to_col(HKr).op('r').to_col(HKf).op('s').op('b')          # r HK=K ; reenq ; BP=K
    link(c,22,down=c.x+1)                                      # -> (2,22) E
    rc=22
    C(2,rc,'>'); C(3,rc,'d')
    C(3,rc+1,'v'); C(3,rc+2,'>')                               # drop into body lane rc+2 heading E
    cbody=Cur(P,4,rc+2,E).litE(OFFSET)                         # A=OFFSET
    cbody.to_col(SCf).op('s').op('m')                          # s SC ; m
    cbody.turn(S).turn(Wd).to_col(2).turn(N).to_row(rc)       # loop up col2 to (2,rc)'>'
    cdone=Cur(P,4,rc,E)                                        # exit d straight E (A junk)
    # route EAST past the SeedC body literal, drop, then back to col2 for a clean E work lane
    cdone.to_col(14).turn(S).to_row(28).turn(Wd).to_col(1).turn(S).to_row(29).turn(E)
    cdone.to_col(HMr).op('r').to_col(HMf).op('s')       # r HM=M ; s reenq  (A=M)
    cdone.to_col(HMRf).op('s')                          # s HMR <- M  (Mrem init)  (A=M)
    cdone.op('1').op('N')                               # A=-1 (SC_SENT)
    cdone.to_col(SCf).op('s')                           # s SC <- SENT
    cdone.turn(S).to_row(30).turn(Wd).to_col(1).turn(S) # onto FETCHA highway col1, heading S
    go_fetcha(cdone)                                    # glide down col1 to (1,FETY)'>'

    # ================= RUNTIME =================  (FETCHA highway = col1, turn '>' @ FETY only)
    FE=FETY   # 32
    # ---- FETCHA lane (row FE, E from (2,FE)) ----
    f=Cur(P,2,FE,E)
    f.to_col(SAr).op('r').op('M')          # r SA=a ; B=a
    f.litE(500).op('-')                    # A=500-a  (B=a)
    cwc,ccwc,_=f.X()                        # A>0 real -> CW(S) BLOCK ; A<0 SENT -> CCW(N) HALT
    ccwc.op('H')                           # HALT (one cell north of X)
    # ---- BLOCK (cwc heading S ; B=a) : load a into H1, BP=K ----
    blk=cwc; blk.to_row(FE+2).turn(E)      # -> row FE+2 (34), E
    blk.to_col(HKr).op('r').op('b')        # r HK=K ; BP=K   (B=a)
    blk.to_col(H1r).op('r').op('W').op('s')# r H1 discard ; W A=a,B=old ; s H1 push a
    # route into KLOOP entry (H1r, KY) via convergence cell (H1r-1, KY)='>'
    KY=FE+4                                 # 36
    # route on row FE+2 (above KLOOP) west to H1r-1, then down to KLOOP entry '>' @ (H1r-1,KY)
    blk.turn(Wd).to_col(H1r-1).turn(S).to_row(KY).turn(E)   # converge '>' @ (H1r-1,KY) -> (H1r,KY)
    # ---- KLOOP (row KY, E) ----
    k=Cur(P,H1r,KY,E)
    k.op('r')                               # (H1r) r H1 -> A=a
    k.to_col(H1f).op('s').op('M')           # s H1 reenq ; B=a
    k.to_col(SBr).op('r').op('s').op('*').op('M')   # r SB=b ; s reenq ; A=a*b ; B=a*b
    k.to_col(SCr).op('r').op('+').op('s').op('m')   # r SC=c ; A=c+ab ; s store ; BP--
    kcw,kst=k.d_()                          # BP>0 CW(S) loop ; else straight(E) POSTK
    # loop-back: kcw(S) -> W -> N -> converge at (H1r-1,KY)'>' -> E into KLOOP
    kcw.turn(Wd).to_col(H1r-1).turn(N).to_row(KY).turn(E)
    # ---- POSTK (kst heading E) : realign SC ; then dec Mrem (vertical gadget @ col HMRr) ----
    pk=kst; pk.turn(S).to_row(KY+3).turn(Wd).to_col(SCr-1).turn(S).turn(E)  # -> clean E lane @ SCr
    pk.op('r').to_col(SCf).op('s')          # r SC pop SENT ; s SC reenq (realign)
    pk.turn(S).to_row(KY+5).turn(Wd).to_col(HMRr).turn(S)      # approach col HMRr heading S
    pk.op('r').op('M').op('1').op('-').op('N')   # down: A=Mrem;B=Mrem;A=1;A=1-Mrem;A=Mrem-1
    pk.turn(E).op('s')                      # (HMRf) s HMR push Mrem-1
    dcw,dccw,dst=pk.X()                     # A>0 CW(S) more-blocks->FETCHA ; A==0 straight(E) ROWEND
    dcw.turn(S) if dcw.d!=S else None
    dcw.to_row(KY+12).turn(Wd).to_col(1).turn(N); go_fetcha(dcw)  # up col1 -> FETCHA
    # ---- ROWEND (dst heading E) : go to OUTLOOP (col2 highway, '>' @ OY) ----
    OY=52
    C(2,OY,'>')                             # OUTLOOP convergence cell (col2 blank elsewhere in runtime)
    def go_outloop(c): assert c.x==2,(c.x,c.y,c.d); c.to_row(OY)
    dst.turn(S).to_row(50).turn(Wd).to_col(2).turn(S); go_outloop(dst)   # down into (2,OY)
    # ---- OUTLOOP lane (row OY, E from (3,OY)) ----
    ol=Cur(P,3,OY,E).to_col(SCr).op('r')    # r SC -> A=v
    ecw,eccw,_=ol.X()                       # v>0 emit -> CW(S) ; v<0 SENT -> CCW(N)
    # ---- emit (ecw heading S) : real=v-OFFSET -> O ; reset OFFSET ; loop OUTLOOP ----
    em=ecw; em.turn(Wd).to_col(3).turn(S).to_row(OY+2).turn(E)   # emit lane
    em.op('M').litE(OFFSET).op('W').op('-') # B=v ; A=OFFSET ; W A=v,B=OFFSET ; - A=real
    em.to_col(O_).op('s')                   # emit real
    em.turn(S).to_row(OY+3).turn(Wd).to_col(3).turn(E)          # reset lane
    em.litE(OFFSET).to_col(SCf).op('s')     # A=OFFSET ; s SC push OFFSET
    em.turn(S).to_row(OY+4).turn(Wd).to_col(2).turn(N); go_outloop(em)  # loop back up col2
    # ---- SENT (eccw heading N) : push SENT ; reset Mrem=M ; -> FETCHA ----
    dn=eccw; dn.turn(E).to_col(48).turn(S).to_row(OY+6).turn(Wd).to_col(3).turn(E)  # descend via col48
    dn.op('1').op('N').to_col(SCf).op('s')  # A=-1 ; s SC push SENT
    dn.turn(S).to_row(OY+7).turn(Wd).to_col(3).turn(E)          # reset lane
    dn.to_col(HMr).op('r').to_col(HMf).op('s').to_col(HMRf).op('s')  # r HM=M;reenq;s HMR (reset Mrem)
    dn.turn(S).to_row(OY+8).turn(Wd).to_col(1).turn(N); go_fetcha(dn)  # up col1 -> FETCHA

    return P

if __name__=="__main__":
    import sys
    P=build(sys.argv[1] if len(sys.argv)>1 else "tiny")
    print(P.p.render()); print("footprint",P.p.footprint())
