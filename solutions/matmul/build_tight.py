"""Matmul littleman builder — COUNTER-DRIVEN tight-MAC machine (from scratch).  [WIP]

STATUS: PASSES 7/7 on the wasm oracle (stage 'big').  avgTicks 55718 (~= opt5's 49864).
  box 128164 (56x358) because SA/SB are DEEP straight rings -> score 7.14B (worse than opt5
  ONLY due to the unfolded box; per-tick speed already ties opt5).
Two remaining levers to BEAT opt5 (185M local / 230M server), both understood:
  A) COMPACT-FOLD SA/SB beside/into the CTRL so height stops driving the box.  Deep straight
     rings (DA=-292, DB=-272) give the 358 height.  A beside-hang serpentine (opt5 hang_ring,
     no added height; SA cap>=NM+1<=257, SB cap>=MK<=256; GAP col between legs -> no
     short-circuit; H1 MUST stay shallow -re-read every MAC) -> box ~4300.  folded_on()/pipeC
     helpers are already ported below.
  B) TIGHTEN KLOOP: it is a single eastbound row (mouths spread cols 33-46) + a ~16-cell
     return corridor = ~32 cells/MAC (glide 48% per xray).  Cluster H1/SB/SC mouths adjacent
     + 2-row rectangle -> ~16 cells/MAC -> avgTicks ~30k.  A+B together: ~4300 x 30k ~= 130M.
Fixed to get here (all real oracle bugs): seed-phase man-flow connections; literals ->
  shift-computed constants (build_offset/build_sasent, no backticks); H1 dummy seed; HK reenq
  in BLOCK; BLOCK->KLOOP glide intercept; SENT-lane west-then-east self-crossings; Mrem drain
  on row-boundary; H1 shallow (deep H1 stalled 68t/MAC).
FALLBACK: solutions/matmul/matmul-opt5.man (185M local / 230M server, RANK 2) stays best.

Algorithm validated in model_tight.py.  Key vs opt5:
  * SB flat (no marks) -> inner K-loop driven by a BP counter (no per-MAC MARK classify).
  * a-fetch via SA tokens (a | SA_SENT); row boundary via per-row block counter Mrem.
  * a held in holder H1 across K-sweep (round-trips each MAC).  SC=[c..,SC_SENT] stationary.

Rings: SA=[a..,SENT], SB=[b..](cycled), SC; holders H1(a), HK(K), HM(M), HMR(Mrem).
Columns are VARIABLES; 'tiny' uses a spread staggered (deeper-left) straight-ring layout
that is collision-free (FSM correctness on small cases).  'run' will cluster+fold later.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys, os
sys.path.insert(0, _REPO + "/tools")
import littleman as lm

OFFSET=262144; SA_SENT=16384; SC_SENT=-1   # OFFSET=1<<18 (> max|c|~156816); SA_SENT=1<<14
# constants BUILT via digit+shift op-sequences (no backtick literals -> no vertical-literal clash).
# Each helper takes an E-heading cursor, leaves A=const (B scratched).
def build_offset(c): c.op('9').op('M').op('+').op('M').op('1').op('{')  # A=9;B=9;A=18;B=18;A=1;A=1<<18
def build_sasent(c): c.op('7').op('M').op('+').op('M').op('1').op('{')  # A=7;B=7;A=14;B=14;A=1;A=1<<14

# ---- spread columns (tiny), deeper-left staggered relays ----
I_=2
SAf=5;   SAr=7        # SA: gap col6 between feed/ret (avoids deep-ring short-circuit)
HMr=11;  HMf=12       # holders: ret<feed so eastward "r then s-reenq" walks monotonically
HKr=17;  HKf=18
HMRr=23; HMRf=24      # Mrem: adjacent (dec is a vertical gadget at col HMRr)
H1r=33;  H1f=35       # gap 34
SBr=38;  SBf=40       # SB: gap col39 between ret/feed (avoids deep-ring short-circuit)
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
    def get(s,x,y): return s.placed.get((x,y),' ')
    def pipeC(s,points):
        cells=[]
        for i in range(len(points)-1):
            (x0,y0),(x1,y1)=points[i],points[i+1]
            dx=(x1>x0)-(x1<x0); dy=(y1>y0)-(y1<y0)
            for k in range(abs(x1-x0)+abs(y1-y0)): cells.append((x0+dx*k,y0+dy*k,dx,dy))
        lx,ly=points[-1]; cells.append((lx,ly,cells[-1][2],cells[-1][3]))
        for idx,(x,y,dx,dy) in enumerate(cells):
            bend=idx>0 and (cells[idx-1][2],cells[idx-1][3])!=(dx,dy)
            ch=lm.VEC2ARROW[(dx,dy)] if (idx==0 or idx==len(cells)-1 or bend) else ('-' if dx!=0 else '|')
            cur=s.get(x,y)
            if cur!=' ' and cur!=ch: raise SystemExit(f"PIPE COLLISION {(x,y)}: {cur!r} vs {ch!r}")
            s.C(x,y,ch)

# ---- serpentine fold helpers (from build_opt5, proven) ----
def _serp_up(cols, ytop, bot):
    pts=[(cols[0],-1),(cols[0],ytop)]; at_top=True
    for c in cols[1:]:
        pts.append((c, ytop if at_top else bot))
        if at_top: pts.append((c,bot)); at_top=False
        else:      pts.append((c,ytop)); at_top=True
    return pts, cols[-1], at_top
def _serp_down(cols, ytop, bot, start_row, end=-1):
    if len(cols)==1: return [(cols[0],start_row),(cols[0],end)]
    pts=[(cols[0],start_row),(cols[0],bot)]; at_bot=True
    for c in cols[1:]:
        pts.append((c, bot if at_bot else ytop)); last=(c==cols[-1])
        if at_bot: pts.append((c, end if last else ytop)); at_bot=False
        else:      pts.append((c, end if last else bot)); at_bot=True
    return pts
def _relay(P, RL, RT):
    P.p.room(RL,RT,6,4)
    P.C(RL+1,RT+1,'@'); P.C(RL+2,RT+1,'>'); P.C(RL+3,RT+1,'R'); P.C(RL+4,RT+1,'v')
    P.C(RL+2,RT+2,'^'); P.C(RL+3,RT+2,'s'); P.C(RL+4,RT+2,'<')
def folded_on(P, feed_cols, ret_cols, ytop, bot, RT, relay_left=None, feed_in=None, ret_out=None, ret_top=None):
    RB=RT+3
    if relay_left is None: relay_left=ret_cols[0]-2
    if feed_in is None:    feed_in=relay_left+4
    if ret_out is None:    ret_out=ret_cols[0]
    if ret_top is None:    ret_top=RB+3
    _relay(P, relay_left, RT)
    fpts,fx,ftop=_serp_up(feed_cols, ytop, bot)
    P.pipeC(fpts + [(fx, RT-2),(feed_in, RT-2),(feed_in, RT-1)])
    rpts=_serp_down(ret_cols, ret_top, bot, RB+1)
    if ret_out!=ret_cols[0]: rpts=[(ret_out,RB+1)]+rpts
    P.pipeC(rpts)

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
    W=56; H=66
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
    # SA/SB deepened for large cases (SA cap>=NM+1<=257, SB cap>=MK<=256); gaps avoid short-circuit.
    DA,DB = (-70,-40) if stage=="tiny" else (-292,-272)
    ring(SAf,SAr,DA); ring(HMf,HMr,-64); ring(HKf,HKr,-58); ring(HMRf,HMRr,-52)
    # H1 (a-holder) re-read EVERY MAC with only 1 value -> MUST be shallow (round-trip latency
    # else the man stalls each MAC waiting for a to cycle back).  SC re-read hot too -> shallow.
    ring(H1f,H1r,-9); ring(SBf,SBr,DB); ring(SCf,SCr,-14)
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
    c=Cur(P,4,7,E); build_sasent(c)            # racetrack exit (BP=0) -> A=SA_SENT (built, cols4-9)
    c.turn(S).turn(Wd).to_col(SAf).op('s')     # v@(10,7); west row8 to col5; s SA<-SENT ; cursor (4,8)W
    # link to SeedB: DOWN col4 (below SeedA body cols3 rows8-11) then turn E into SeedB (row12)
    c.turn(S).to_row(12).turn(E)               # 'v'@(4,8) down to (4,12) '>' -> E into SeedB

    # ================= SEED-B : BP=MK ; loop r I -> s SB =================
    c.to_col(HMr).op('r').to_col(HMf).op('s').op('M')          # r HM=M ; reenq ; B=M
    c.to_col(HKr).op('r').to_col(HKf).op('s').op('*').op('b')  # r HK=K ; reenq ; A=MK ; BP=MK
    link(c,14,down=c.x+1)                                       # -> (2,14) E
    C(2,14,'>'); C(3,14,'d')                                   # racetrack entry ; BP>0 CW E->S
    C(3,15,'r'); C(3,16,'>')                                   # body: r I -> A=b (S) ; turn E
    bl=Cur(P,4,16,E).to_col(SBf).op('s').op('m')               # s SB ; m  (row16)
    bl.turn(S).turn(Wd).to_col(2).turn(N).to_row(14)           # loop up col2 -> (2,14)'>'
    c=Cur(P,4,14,E)                                            # racetrack exit (BP=0)

    # ================= SEED-C : BP=K ; loop OFFSET->SC ; SC_SENT ; HMR<-M =================
    link(c,20,down=15)                                         # -> (2,20) E (row19 leg clear of SeedB bl@row17)
    c.to_col(HKr).op('r').to_col(HKf).op('s').op('b')          # r HK=K ; reenq ; BP=K
    link(c,24,down=c.x+1)                                      # -> (2,24) E
    rc=24
    C(2,rc,'>'); C(3,rc,'d')
    C(3,rc+1,'v'); C(3,rc+2,'>')                               # drop into body lane rc+2 heading E
    cbody=Cur(P,4,rc+2,E); build_offset(cbody)                # A=OFFSET (built, cols4-9)
    cbody.to_col(SCf).op('s').op('m')                          # s SC ; m
    cbody.turn(S).turn(Wd).to_col(2).turn(N).to_row(rc)       # loop up col2 to (2,rc)'>'
    cdone=Cur(P,4,rc,E)                                        # exit d straight E (A junk)
    # route EAST past the SeedC body literal, drop, then back to col2 for a clean E work lane
    cdone.to_col(14).turn(S).to_row(28).turn(Wd).to_col(1).turn(S).to_row(29).turn(E)
    cdone.to_col(HMr).op('r').to_col(HMf).op('s')       # r HM=M ; s reenq  (A=M)
    cdone.to_col(HMRf).op('s')                          # s HMR <- M  (Mrem init)  (A=M)
    cdone.to_col(H1f).op('s')                           # s H1 <- M  (DUMMY seed; first BLOCK discards it)
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
    blk.to_col(HKr).op('r').to_col(HKf).op('s').op('b')   # r HK=K ; reenq ; BP=K   (B=a)
    blk.to_col(H1r).op('r').op('W').op('s')# r H1 discard ; W A=a,B=old ; s H1 push a
    KY=FE+4                                 # 36
    # route DOWN to row FE+3, then west (below the H1 load) to the KLOOP convergence '>' @ (H1r-1,KY)
    blk.turn(S).turn(Wd).to_col(H1r-2).turn(S).to_row(KY).turn(E)   # -> (H1r-1,KY)'>' -> (H1r,KY)
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
    build_offset(dst); dst.op('M')          # A=OFFSET ; B=OFFSET  (resident across OUTLOOP)
    dst.turn(S).to_row(50).turn(Wd).to_col(2).turn(S); go_outloop(dst)   # down into (2,OY)
    # ---- OUTLOOP lane (row OY, E from (3,OY)) : B holds OFFSET throughout ----
    ol=Cur(P,3,OY,E).to_col(SCr).op('r')    # r SC -> A=v  (B=OFFSET)
    ecw,eccw,_=ol.X()                       # v>0 emit -> CW(S) ; v<0 SENT -> CCW(N)
    # ---- emit (ecw heading S ; A=v, B=OFFSET) : real=v-OFFSET -> O ; reset OFFSET ; loop ----
    em=ecw; em.turn(Wd).to_col(3).turn(S).to_row(OY+2).turn(E)   # emit lane
    em.op('-')                              # A=v-OFFSET=real (B=OFFSET)
    em.to_col(O_).op('s').op('W')           # emit real ; W A=OFFSET,B=real
    em.turn(S).to_row(OY+3).turn(Wd).to_col(SCf).op('s').op('M')  # reset lane (W): s SC push OFFSET ; M restore B
    em.turn(S).to_row(OY+4).turn(Wd).to_col(2).turn(N); go_outloop(em)  # loop back up col2
    # ---- SENT (eccw heading N ; A=SENT=-1) : push SENT ; reset Mrem=M ; -> FETCHA ----
    #   descend via col53 (east of emit lanes, which reach only col52) to rows below emit.
    #   one WESTWARD pass on row OY+6 (no east-detour): push SENT, drain stale Mrem, reach col3.
    dn=eccw; dn.turn(E).to_col(53).turn(S).to_row(OY+6).turn(Wd)  # descend col53, head W on row OY+6
    dn.to_col(SCf).op('s')                  # s SC push SENT (A=-1 from OUTLOOP read)
    dn.to_col(HMRr).op('r')                 # r HMR : DRAIN stale Mrem
    dn.to_col(3).turn(S).to_row(OY+8).turn(E)                   # down to reset lane
    dn.to_col(HMr).op('r').to_col(HMf).op('s').to_col(HMRf).op('s')  # r HM=M;reenq;s HMR (push M)
    dn.turn(S).to_row(OY+9).turn(Wd).to_col(1).turn(N); go_fetcha(dn)  # up col1 -> FETCHA

    return P

if __name__=="__main__":
    import sys
    P=build(sys.argv[1] if len(sys.argv)>1 else "tiny")
    print(P.p.render()); print("footprint",P.p.footprint())
