import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

def build(n=16, rowstep=1, minrow=5):
    """Flat reader (count-discard, r/s per lane, halt), nested lanes -> vertical merger.
    Single round. Lane i mouth col = 4+2i; merger entries rows minrow..(minrow+ (n-1)*rowstep),
    lane0 deepest (bottom, reading-order last), lane n-1 shallowest (top, reading-order first)."""
    p = lm.Program(); P = p.put
    # Reader room: interior row 1, cols 1..(2n+3). south wall row 2, mouths at row3.
    lastcol = 4 + 2*(n-1)         # last s col
    Wr = lastcol + 4
    p.room(0, 0, Wr, 3)
    P(1,1,"@"); P(2,1,"r")        # read count into A, discard
    for i in range(n):
        rc = 3+2*i; sc = 4+2*i
        P(rc,1,"r"); P(sc,1,"s")
    P(lastcol+2,1,"H")            # safe halt after last send
    # Input room -> reader top wall col1
    p.input_room(0,-5); p.pipe([(1,-2),(1,-1)])
    # Merger vertical room to the right. west wall col MX.
    MX = lastcol + 3             # e.g. n=16 -> 34+3=37
    rows = [minrow + (n-1-i)*rowstep for i in range(n)]  # lane i row; i=0 -> deepest(bottom)
    R0 = max(rows); Rtop = min(rows)
    # merger room spans rows Rtop-1 .. R0+1, cols MX .. MX+5
    Mtop = Rtop-1; Mbot = R0+1
    p.room(MX, Mtop, 6, Mbot-Mtop+1)
    # lanes: down col Mi from row3 to Ri, then east to (MX-1, Ri)
    for i in range(n):
        Mi = 4+2*i; Ri = rows[i]
        p.pipe([(Mi,3),(Mi,Ri),(MX-1,Ri)])
    # merger man racetrack (rows Rtop..Rtop+1 near top interior), loop R ; s
    a = Rtop
    P(MX+1,a,">"); P(MX+2,a,"@"); P(MX+3,a,"R"); P(MX+4,a,"v")
    P(MX+4,a+1,"<"); P(MX+3,a+1,"s"); P(MX+2,a+1,"<"); P(MX+1,a+1,"^")
    # output room to the right of merger, incoming on merger east wall row a+1
    OX = MX+9
    p.output_room(OX, a)
    p.pipe([(MX+6,a+1),(MX+8,a+1)])   # merger east wall (MX+5) -> pipe -> O west (OX)
    return p

if __name__ == "__main__":
    import json
    n = int(sys.argv[1]) if len(sys.argv)>1 else 16
    rowstep = int(sys.argv[2]) if len(sys.argv)>2 else 1
    p = build(n, rowstep)
    print(p.render())
    print("footprint:", p.footprint())
    p.save(os.path.join(os.path.dirname(__file__), f"dlN.man"))
