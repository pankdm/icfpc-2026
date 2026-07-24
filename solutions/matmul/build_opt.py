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
    def pipeC(self,points):
        """collision-checked pipe (arrows at start/bends/end, body glyphs between).
        Also checks against ALL existing program cells (room walls, other pipes)."""
        cells=[]
        for i in range(len(points)-1):
            (x0,y0),(x1,y1)=points[i],points[i+1]
            dx=(x1>x0)-(x1<x0); dy=(y1>y0)-(y1<y0)
            for k in range(abs(x1-x0)+abs(y1-y0)):
                cells.append((x0+dx*k,y0+dy*k,dx,dy))
        lx,ly=points[-1]; cells.append((lx,ly,cells[-1][2],cells[-1][3]))
        for idx,(x,y,dx,dy) in enumerate(cells):
            bend = idx>0 and (cells[idx-1][2],cells[idx-1][3])!=(dx,dy)
            ch = lm.VEC2ARROW[(dx,dy)] if (idx==0 or idx==len(cells)-1 or bend) else ('-' if dx!=0 else '|')
            cur=self.p.get(x,y)
            if cur!=' ' and cur!=ch:
                raise SystemExit(f"PIPE COLLISION {(x,y)}: existing {cur!r} vs pipe {ch!r}")
            self.C(x,y,ch)

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

    # ---- FOLDED ring (SA/SB): feed serpentine + return serpentine, split so no
    # column is shared; relay above; feed wired over the top into relay top wall. ----
    def serp_up(cols, ytop, bot):
        """serpentine feed: (cols[0],-1) up to ytop, alternating; returns pts,end,at_top."""
        pts=[(cols[0],-1),(cols[0],ytop)]; at_top=True
        for c in cols[1:]:
            pts.append((c, ytop if at_top else bot))
            if at_top: pts.append((c,bot)); at_top=False
            else:      pts.append((c,ytop)); at_top=True
        return pts, cols[-1], at_top
    def serp_down(cols, ytop, bot, start_row):
        """serpentine return: from relay bottom at (cols[0],start_row) going DOWN,
        serpentine, end at (cols[-1],-1)."""
        if len(cols)==1: return [(cols[0],start_row),(cols[0],-1)]
        pts=[(cols[0],start_row),(cols[0],bot)]; at_bot=True
        for c in cols[1:]:
            pts.append((c, bot if at_bot else ytop)); last=(c==cols[-1])
            if at_bot: pts.append((c, -1 if last else ytop)); at_bot=False
            else:      pts.append((c, -1 if last else bot)); at_bot=True
        return pts
    def folded(feed_cols, ret_cols, H, RT, relay_left=None, feed_in=None, ret_out=None):
        """Fold one ring. feed serpentine (feed_cols, ODD count -> ends TOP) on feed side;
        return serpentine (ret_cols, ret_cols[0]=far end, ret_cols[-1]=attach col) on
        return side; relay at top-wall row RT (cols relay_left..relay_left+5); feed-end
        wired OVER the top (row RT-2, above the relay) into the relay's top wall.
        ret_out = relay bottom-wall interior col the return exits from; if it differs from
        ret_cols[0], a horizontal LEAD (row RB+1, above the serpentines) connects them."""
        ytop=-H; bot=-3
        RB=RT+3                         # relay bottom-wall row
        if relay_left is None: relay_left=ret_cols[0]-2
        if feed_in is None:    feed_in=relay_left+4
        if ret_out is None:    ret_out=ret_cols[0]
        p.room(relay_left,RT,6,4)
        C(relay_left+1,RT+1,'@'); C(relay_left+2,RT+1,'>'); C(relay_left+3,RT+1,'R'); C(relay_left+4,RT+1,'v')
        C(relay_left+2,RT+2,'^'); C(relay_left+3,RT+2,'s'); C(relay_left+4,RT+2,'<')
        # feed serpentine ends at TOP; wire UP above the relay (RT-2), across to feed_in, down into top wall
        fpts,fx,ftop=serp_up(feed_cols, ytop, bot)
        feed_pts = fpts + [(fx, RT-2),(feed_in, RT-2),(feed_in, RT-1)]
        b.pipeC(feed_pts)              # last cell (feed_in,RT-1) fwd S -> (feed_in,RT) top wall
        # return exits relay bottom wall at ret_out, optional lead to ret_cols[0], then
        # serpentines down. Turn cols must NOT run adjacent to the relay wall (spurious
        # attach breaks delivery) -> turns start 2 rows below (RB+3).
        rpts=serp_down(ret_cols, RB+3, bot, RB+1)
        if ret_out!=ret_cols[0]:
            rpts=[(ret_out,RB+1)]+rpts     # lead: exit ret_out -> east/west to ret_cols[0] at RB+1
        b.pipeC(rpts)

    if stage in ("run","full"):
        # small rings + IO FIRST so folded pipeC checks against them.
        ring(SCf,SCr, SCf-1, -13)   # SC short straight (cap ~19>=17), relay cols 16..21
        ring(H1f,H1r, 21, -8)       # H1 tiny, relay cols 21..26 (clear of O room 27..29)
        IY=-6
        p.input_room(I_-1,IY); p.pipe([(I_,IY+3),(I_,-1)])
        p.output_room(O_-1,IY); p.pipe([(O_,-1),(O_,IY+3)])
        # SA: feed serpentine LEFT. col5 riser then ONE top connector jumps over the whole
        #     I-room span (cols 1..4) into the negative cols; ODD count -> ends TOP. return
        #     straight col6. relay above feed-end; RT lifted above SB feed wire.
        #     SA relay at cols 1..6 (OFF SB feed cols 7..11) so it can sit low (RT=-34)
        #     instead of being lifted above SB's feed wire. return exits col4, leads E to col6.
        folded([5,0,-1,-2,-3,-4,-5,-6,-7], [6], 29, -34, relay_left=1, feed_in=3, ret_out=4)
        # SB: feed serpentine cols 11..7 (ODD->top), return serpentine cols 15..12 (avoid
        #     SC relay at cols 16..21). RT above SB serpentine. H sized for cap M*(K+1)=272.
        folded([11,10,9,8,7], [15,14,13,12], 37, -41)
    else:
        big = -145; scy=-24
        ring(SAf,SAr, SAf-1, big); ring(SBf,SBr, SBf-1, big)
        ring(SCf,SCr, SCf-1, scy); ring(H1f,H1r, H1f-1, -8)
        IY=-16
        p.input_room(I_-1,IY)
        p.pipe([(I_,IY+3),(I_,-1)])
        p.output_room(O_-1,IY)
        p.pipe([(O_,-1),(O_,IY+3)])

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
        C(31,43,'<'); C(25,43,'v')                  # real (south) -> west to col25 highway -> down

        # ---- MAIN read (row48, westward, entry (34,48)) ----
        #   r SB -> A=x ; s SB reenq ; M B=x ; then classify
        C(25,48,'<')
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
        C(15,54,'v'); C(15,55,'>'); C(25,55,'^')

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

def compact(out):
    """Strip fully-blank ('|'-only) interior rows of the CTRL room (Tier 1)."""
    rows=out.split("\n")
    w=max(len(r) for r in rows); rows=[r.ljust(w) for r in rows]
    # find CTRL room top wall row (first '+---...' after some content) and bottom wall
    walls=[i for i,r in enumerate(rows) if r.lstrip().startswith('+') and set(r.strip())<= set('+-')]
    # CTRL room is the LAST such pair (top/bottom). Use the largest room.
    top=min(i for i in walls); # not robust; fall back to explicit detection below
    # detect the CTRL room: the widest '+---+' wall
    widest=max(walls, key=lambda i: len(rows[i].strip()))
    tops=[i for i in walls if len(rows[i].strip())==len(rows[widest].strip())]
    ctop,cbot=min(tops),max(tops)
    keep=[r for i,r in enumerate(rows) if not (ctop<i<cbot and (set(r)-{' '})=={'|'})]
    return "\n".join(x.rstrip() for x in keep)+"\n"

if __name__=="__main__":
    import sys
    stage = sys.argv[1] if len(sys.argv)>1 else "run"
    b=build(stage=stage)
    out = b.p.render()+"\n"
    if stage in ("run","full"):
        out = compact(out)
        open(os.path.join(os.path.dirname(__file__),"matmul-opt.man"),"w").write(out)
    print(out)
    print("footprint",b.p.footprint())
