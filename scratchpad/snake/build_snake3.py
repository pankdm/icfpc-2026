import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import os, sys
sys.path.insert(0, _REPO + "/tools")
import littleman as lm

# Snake v3: count-send W/s folded onto the SPAWN row (left of @, executed only on
# loop-return) -> removes the 2 dedicated corridor rows (SROW/WROW) with NO width change.
def build(NL=16):
    p = lm.Program(); P = p.put
    XL = 6
    XR = XL + NL - 1
    RW = max(XR + 2, 14)
    # reader rows (SROW/WROW gone)
    SPAWN, RTOP, RT, M1, M2, M3, RB, RBOT = 1,2,3,4,5,6,7,8
    WALL_B = 9
    p.room(0, 0, RW, WALL_B+1)          # rows 0..9

    p.input_room(2, -5)                 # I at (3,-4)
    p.pipe([(3,-2),(3,-1)])             # into reader top (3,0)

    # spawn row: > W s @ r M b   ('>' return-turn; W,s count-send done only on loop)
    P(1,SPAWN,">"); P(2,SPAWN,"W"); P(3,SPAWN,"s"); P(4,SPAWN,"@")
    P(5,SPAWN,"r"); P(6,SPAWN,"M"); P(7,SPAWN,"b")
    P(XR,SPAWN,"v"); P(XR,RTOP,"v")     # feeder descent + RTOP passthrough at XR

    for c in range(XL, XR+1):
        j = XR - c
        if j % 2 == 0:  # down
            P(c,RT,"v"); P(c,M1,"r"); P(c,M2,"m"); P(c,M3,"s"); P(c,RB,"d")
        else:           # up
            P(c,RT,"a"); P(c,M1,"s"); P(c,M2,"m"); P(c,M3,"r"); P(c,RB,"^")
    for c in range(2, XR+1):
        if p.get(c,RTOP)==" ": P(c,RTOP,"<")
        if p.get(c,RBOT)==" ": P(c,RBOT,"<")
    # col1 corridor up: RTOP..RBOT = ^ ; SPAWN col1 already '>'
    for r in range(RTOP, RBOT+1):
        P(1,r,"^")

    S = WALL_B                          # 9
    for c in range(XL, XR+1):
        p.pipe([(c,S+1),(c,S+2)])       # (c,10),(c,11) -> collector north (c,12)

    # collector
    CN = S+3                            # 12
    Ci = CN+1                           # 13
    p.room(0, CN, RW, 5)               # rows 12..16
    P(1,Ci,">"); P(2,Ci,"@"); P(3,Ci,"r"); P(4,Ci,"b"); P(5,Ci,">")
    P(6,Ci,"R"); P(7,Ci,"s"); P(8,Ci,"m"); P(9,Ci,"d")
    P(9,Ci+1,"<"); P(8,Ci+1,"<"); P(7,Ci+1,"<"); P(6,Ci+1,"<"); P(5,Ci+1,"^")
    P(10,Ci,"v"); P(10,Ci+1,"v")
    for c in range(1,11):
        if p.get(c,Ci+2)==" ": P(c,Ci+2,"<")
    P(1,Ci+2,"^"); P(1,Ci+1,"^")

    # count pipe: reader west (0,SPAWN) -> around west -> collector west (0,Ci)
    p.pipe([(-1,SPAWN),(-2,SPAWN),(-2,Ci),(-1,Ci)])

    CB = CN+4                           # 16 south wall
    p.output_room(0, CB+3)             # O rows 19..21
    p.pipe([(1,CB+1),(1,CB+2)])         # (1,17),(1,18) -> O top (1,19)
    return p

if __name__ == "__main__":
    NL = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    p = build(NL)
    out = _REPO + "/scratchpad/snake/snake3.man"
    p.save(out)
    print(p.render())
    print("footprint:", p.footprint())
