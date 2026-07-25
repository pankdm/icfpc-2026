import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
import littleman as lm

def build(NL=16):
    p = lm.Program(); P = p.put
    XL = 6                           # lanes col XL..XR; spawn '>@rbM' occupies cols1..5 on SPAWN row
    XR = XL + NL - 1
    RW = max(XR + 2, 13)             # reader cols 0..RW-1 (XR at RW-2); floor for collector loop
    # reader rows
    SPAWN, SROW, WROW, RTOP, RT, M1, M2, M3, RB, RBOT = 1,2,3,4,5,6,7,8,9,10
    WALL_B = 11
    p.room(0, 0, RW, WALL_B+1)       # rows 0..11

    # input room + pipe above spawn r (col3)
    p.input_room(2, -5)              # I at (3,-4)
    p.pipe([(3,-2),(3,-1)])          # into reader top wall (3,0)

    # spawn row
    P(1,SPAWN,">"); P(2,SPAWN,"@"); P(3,SPAWN,"r"); P(4,SPAWN,"b"); P(5,SPAWN,"M")
    P(XR,SPAWN,"v"); P(XR,SROW,"v"); P(XR,WROW,"v"); P(XR,RTOP,"v")

    # lanes
    for c in range(XL, XR+1):
        j = XR - c
        if j % 2 == 0:  # down
            P(c,RT,"v"); P(c,M1,"r"); P(c,M2,"m"); P(c,M3,"s"); P(c,RB,"d")
        else:           # up
            P(c,RT,"a"); P(c,M1,"s"); P(c,M2,"m"); P(c,M3,"r"); P(c,RB,"^")
    # exit lanes RTOP / RBOT run west (cols 2..XR)
    for c in range(2, XR+1):
        if p.get(c,RTOP)==" ": P(c,RTOP,"<")
        if p.get(c,RBOT)==" ": P(c,RBOT,"<")
    # col1 corridor up: rows RBOT..RTOP = ^, WROW=W, SROW=s, SPAWN=>
    for r in range(RTOP, RBOT+1):
        P(1,r,"^")
    P(1,WROW,"W"); P(1,SROW,"s")     # W then s (going up)
    # SPAWN col1 already '>'

    # count pipe: reader west wall (0,SROW) -> down to collector
    S = WALL_B                       # reader south wall row 11
    # column down-pipes
    for c in range(XL, XR+1):
        p.pipe([(c,S+1),(c,S+2)])    # (c,12),(c,13) -> collector north (c,14)

    # ---- collector ----
    CN = S+3                         # 14
    Ci = CN+1                        # 15
    p.room(0, CN, RW, 5)             # rows 14..18 (interior 15,16,17)
    # column pipes into collector north handled above (dst wall CN=14)
    # collector loop
    P(1,Ci,">"); P(2,Ci,"@"); P(3,Ci,"r"); P(4,Ci,"b"); P(5,Ci,">")
    P(6,Ci,"R"); P(7,Ci,"s"); P(8,Ci,"m"); P(9,Ci,"d")
    # inner loop (BP>0): d->S->row Ci+1 west->up to (5,Ci)>
    P(9,Ci+1,"<"); P(8,Ci+1,"<"); P(7,Ci+1,"<"); P(6,Ci+1,"<"); P(5,Ci+1,"^")
    # inner exit (BP==0): d straight E ->(10,Ci) down -> row Ci+2 west -> up col1 -> (1,Ci)>
    P(10,Ci,"v"); P(10,Ci+1,"v")
    for c in range(1,11):
        if p.get(c,Ci+2)==" ": P(c,Ci+2,"<")
    P(1,Ci+2,"^"); P(1,Ci+1,"^")

    # count pipe: reader west wall (0,SROW) -> around west -> collector west wall (0,Ci)
    p.pipe([(-1,SROW),(-2,SROW),(-2,Ci),(-1,Ci)])   # end into collector west wall (0,Ci)

    # output room + pipe from collector south
    CB = CN+4                        # 18 south wall
    p.output_room(0, CB+3)           # O room rows 21..23
    p.pipe([(1,CB+1),(1,CB+2)])      # (1,19),(1,20) -> O top wall (1,21)
    return p

if __name__ == "__main__":
    NL = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    p = build(NL)
    out = "/Users/visenbaev/icfpc26/scratchpad/snake/snake2.man"
    p.save(out)
    print(p.render())
    print("footprint:", p.footprint())
