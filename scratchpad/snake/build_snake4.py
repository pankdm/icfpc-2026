import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import os, sys
sys.path.insert(0, _REPO + "/tools")
import littleman as lm

# Snake v4: MOVE 1 (compress width: XL 6->4, count enters collector at col3-top so the
# count-read clears the data columns col4+) + MOVE 2 (O room to the LEFT of the collector,
# single output pipe -> removes the bottom output stack that padded height).
def build(NL=16, o_left=True):
    p = lm.Program(); P = p.put
    XL = 4
    XR = XL + NL - 1                    # 19
    RW = max(XR + 2, 14)               # 21 -> reader cols 0..20
    SPAWN, RTOP, RT, M1, M2, M3, RB, RBOT = 1,2,3,4,5,6,7,8
    WALL_B = 9
    p.room(0, 0, RW, WALL_B+1)         # rows 0..9

    p.input_room(4, -5)                # I at (5,-4)
    p.pipe([(5,-2),(5,-1)])            # into reader top (5,0)  (above spawn r at col5)

    # spawn row: > W s @ r M b   (@,r,M,b overlap lanes 4..7 at row1; harmless)
    P(1,SPAWN,">"); P(2,SPAWN,"W"); P(3,SPAWN,"s"); P(4,SPAWN,"@")
    P(5,SPAWN,"r"); P(6,SPAWN,"M"); P(7,SPAWN,"b")
    P(XR,SPAWN,"v"); P(XR,RTOP,"v")

    for c in range(XL, XR+1):
        j = XR - c
        if j % 2 == 0:
            P(c,RT,"v"); P(c,M1,"r"); P(c,M2,"m"); P(c,M3,"s"); P(c,RB,"d")
        else:
            P(c,RT,"a"); P(c,M1,"s"); P(c,M2,"m"); P(c,M3,"r"); P(c,RB,"^")
    for c in range(2, XR+1):
        if p.get(c,RTOP)==" ": P(c,RTOP,"<")
        if p.get(c,RBOT)==" ": P(c,RBOT,"<")
    for r in range(RTOP, RBOT+1):
        P(1,r,"^")

    S = WALL_B                         # 9
    for c in range(XL, XR+1):
        p.pipe([(c,S+1),(c,S+2)])      # data columns (c,10),(c,11) -> collector (c,12)

    # collector
    CN = S+3                           # 12
    Ci = CN+1                          # 13
    p.room(0, CN, RW, 5)              # rows 12..16
    P(1,Ci,">"); P(2,Ci,"@"); P(3,Ci,"r"); P(4,Ci,"b"); P(5,Ci,">")
    P(6,Ci,"R"); P(7,Ci,"s"); P(8,Ci,"m"); P(9,Ci,"d")
    P(9,Ci+1,"<"); P(8,Ci+1,"<"); P(7,Ci+1,"<"); P(6,Ci+1,"<"); P(5,Ci+1,"^")
    P(10,Ci,"v"); P(10,Ci+1,"v")
    for c in range(1,11):
        if p.get(c,Ci+2)==" ": P(c,Ci+2,"<")
    P(1,Ci+2,"^"); P(1,Ci+1,"^")

    # count pipe: reader west (0,SPAWN) -> down col-1 -> east (row S+1, left of data col4)
    # -> down into collector top at col3 (clear of data columns col4+)
    p.pipe([(-1,SPAWN),(-1,S+1),(3,S+1),(3,S+2)])   # end (3,S+2=11), attaches south to (3,CN=12)

    # output
    if o_left:
        # O room to the LEFT of the collector; single output pipe from collector west wall
        p.output_room(-5, Ci)          # O rows Ci..Ci+2 at cols -5..-3
        p.pipe([(-1,Ci+1),(-2,Ci+1)])  # collector west (0,Ci+1) -> O east (-3,Ci+1)
    else:
        CB = CN+4
        p.output_room(0, CB+3)
        p.pipe([(1,CB+1),(1,CB+2)])
    return p

if __name__ == "__main__":
    NL = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    ol = (sys.argv[2] != "0") if len(sys.argv) > 2 else True
    p = build(NL, ol)
    out = _REPO + "/scratchpad/snake/snake4.man"
    p.save(out)
    print(p.render())
    print("footprint:", p.footprint())
