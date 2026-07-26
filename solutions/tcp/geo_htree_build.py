"""tcp-geo.man builder — SUBMITTED 6/6 local (9.04M), server 20/20 = 14.22M.

Two-man geometric packet reassembler, lanes = straight vertical 2-cell pipes.
HORIZONTAL decode trees (leaves fan to distinct COLUMNS) so lanes need zero routing
and each collector drain gadget lives in its own column (no pitch-2 collision).

READER (top): preamble discards n, forwards seq (seq-pipe), b(BP=seq), r(val); tree
  steers South on seq&15 to a leaf col; leaf `s`ends val into that lane; returns west,
  waits r[ack] (serialization), loops.
COLLECTOR (bottom): owns waiting in reg B. r(seq); off=seq-waiting; -1 via `b ]]]] d`
  (no constant needed); else W, re-steer to station[waiting&15]; gadget `M q a`:
  fill>=1 -> CCW=East into isolated col+1 drain (r reads lane[k]; col/col+2 tie breaks
  west=col k), drain = r,s(output),1,+ (bumps waiting), re-steer; fill==0 -> straight
  South = EXIT -> s[ack] -> MAIN. off>=16 -> emit -1 (1 N s) + H.

WHY THE ACK: with empty-output rounds, round-gating does NOT serialize the two men, so
the reader could insert an overflow packet (seq=waiting+16 -> lane[waiting&15]) BEFORE
the collector reads that seq to fire -1; the collector would then drain it as a normal
packet. The per-round ACK (collector->reader) makes the reader wait each round, so the
overflow insert can't happen until the collector has offchecked -> -1. Costs ~1.6x
avgTicks (lockstep) but is required for the -1/overflow cases (public + private).

SEMANTICS that shaped this: `q` counts the NEAREST INCOMING pipe only (reader can't
q its outgoing lanes); occupancy-based -1 detection is WRONG (off>=16 fires even with
an empty slot); grading settles at outputSettled so no HALT is required for a pass.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0,_REPO + '/tools')
from layout import Layout, route
W=[8,4,2,1]
def off_h(slot):
    return sum((-W[i] if ((slot>>i)&1) else W[i]) for i in range(4))

def emit_htree(L, x0, y0, leaf_fn):
    """Man enters heading South at (x0,y0-1)->(x0,y0). Nodes rows y0..y0+3; leaves y0+4.
    x: bit1->CW=West, bit0->CCW=East. Returns {slot: leaf_col}."""
    leaves={}
    def node(level,col,row,bits):
        L.put(col,row,'x')
        for bit in (1,0):
            hd=-1 if bit==1 else 1
            w=W[level]
            if level<3: L.put(col+hd,row,']')
            cc=col+hd*w
            L.put(cc,row,'v')
            nb=bits+[bit]
            if level<3:
                node(level+1,cc,row+1,nb)
            else:
                slot=sum(b<<i for i,b in enumerate(nb))
                leaf_fn(L,cc,row+1,slot)
                leaves[slot]=cc
    node(0,x0,y0,[])
    return leaves

if __name__=='__main__':
    L=Layout()
    def lf(L,c,r,s): L.put(c,r,'H')
    lv=emit_htree(L,30,3,lf)
    cols=[lv[s] for s in range(16)]
    print('distinct cols:',len(set(cols))==16, sorted(cols))
    for s in range(16): assert lv[s]==30+off_h(s)
    print('off_h ok')
    print(L.render())

def build_h():
    L=Layout()
    x0=30
    # ---------- READER ----------
    yhr=2
    # preamble East
    L.put(1,yhr,'@'); L.put(2,yhr,'r'); L.put(3,yhr,'>'); L.put(4,yhr,'r')
    L.put(5,yhr,'M'); L.put(6,yhr,'s'); L.put(7,yhr,'b'); L.put(8,yhr,'r')
    L.put(x0,yhr,'v')                      # glide E to x0, turn S into tree
    y0r=yhr+1                              # 3
    def rleaf(L,c,r,s):
        L.put(c,r,'s')                     # r = y0r+4 = 7 ; send val -> lane[s]
        L.put(c,r+1,'<')                   # row 8: turn W to return
    leaves_r=emit_htree(L,x0,y0r,rleaf)
    RB=y0r+4                               # 7 leaf row
    # reader return rail row RB+1=8 -> west to (4,8) r[ack wait] -> up col3 to MAIN
    L.put(4,RB+1,'r')                      # r[ack]: block until collector acks the round
    L.put(3,RB+1,'^')                      # up col3 to (3,yhr) '>' MAIN
    RSW=RB+3                               # reader south wall row = 10 (lanes attach 9? use wall=RB+2=9)
    RWALL=RB+2                             # 9
    L.room(0,yhr-2,x0+18, RWALL-(yhr-2)+1) # reader room encloses preamble..south wall
    # reader I/O
    L.input_room(3,-5); L.pipe([(4,-2),(4,-1)])   # input well above -> reader top wall col4
    # ---------- COLLECTOR ----------
    yhc=26
    CWALL=yhc-2                            # 24 north wall (lanes attach)
    L.put(1,yhc,'@'); L.put(2,yhc,'>'); L.put(3,yhc,'r'); L.put(4,yhc,'-')
    L.put(5,yhc,'b'); L.put(6,yhc,']'); L.put(7,yhc,']'); L.put(8,yhc,']'); L.put(9,yhc,']')
    L.put(10,yhc,'d'); L.put(11,yhc,'W'); L.put(12,yhc,'>'); L.put(13,yhc,'b')
    L.put(x0,yhc,'v')
    y0c=yhc+1                             # 27
    def cleaf(L,c,r,s):
        # station row r=CS heading S: M q a. fill>=1 -> CCW=East -> col c+1 drain (r
        # reads lane[k]: tie between col c and c+2 breaks to west=col c). fill==0 ->
        # straight South in col c = EXIT.
        L.put(c,r,'M'); L.put(c,r+1,'q'); L.put(c,r+2,'a')
        L.put(c+1,r+2,'v'); L.put(c+1,r+3,'r'); L.put(c+1,r+4,'s')
        L.put(c+1,r+5,'1'); L.put(c+1,r+6,'+'); L.put(c+1,r+7,'v')
    leaves_c=emit_htree(L,x0,y0c,cleaf)
    CS=y0c+4
    Rd=CS+8                              # drain rail
    Re=CS+9                             # exit rail
    for s in range(16):
        c=leaves_c[s]
        L.put(c+1,Rd,'<')               # drain drop (col c+1) -> west
        L.put(c,Re,'<')                 # exit straight-S (col c) -> west
    L.put(12,Rd,'^')                    # drain rail -> up col12 -> STEER '>'(12,yhc)
    L.put(2,Re,'^')                     # exit rail  -> up col2 ...
    L.put(2,yhc+1,'s')                  # ... s[ack] to reader ... -> up to MAIN '>'(2,yhc)
    # emit-1 (from d@10 turning S): 1 N ; glide S col10 ; East to output col x0 ; s ; H
    L.put(10,yhc+1,'1'); L.put(10,yhc+2,'N')
    L.put(10,Re+1,'>'); L.put(x0,Re+1,'s'); L.put(x0+1,Re+1,'H')
    BOT=Re+3                            # room bottom (output south wall)
    L.room(0,CWALL-1, x0+22, BOT-(CWALL-1)+1)
    # output pipe: collector south wall (x0,BOT) -> O below
    L.output_room(x0-1, BOT+3); L.pipe([(x0,BOT+1),(x0,BOT+2)])
    # ---------- straight vertical lanes ----------
    for s in range(16):
        c=leaves_r[s]                    # == leaves_c[s]
        L.pipe([(c,RWALL+1),(c,CWALL-2)])
    # seq pipe: reader west wall (0,yhr+1) -> around col-2 -> collector west wall (0,yhc)
    L.pipe([(-1,yhr+1),(-2,yhr+1),(-2,yhc),(-1,yhc)])
    # ack pipe: collector north wall (4,CWALL-1) -> straight up col4 -> reader south wall (4,RWALL)
    L.pipe([(4,CWALL-2),(4,RWALL+1)])
    return L

if False: pass


if __name__=='__main__':
    L=build_h(); print('FOOT',L.footprint())
    L.save(_REPO + '/solutions/tcp/tcp-geo.man')
