import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
import littleman as lm

# Snake v5: v4 (XL=4 + count-col3 + O-left) with the readout LOOP replaced by a
# 2-column serpentine (mirror of the reader) -> ~5 ticks/element vs racetrack ~9.
# R is position-independent so the 2-col oscillation still pulls leftmost-ready = reversed.
def build(NL=16, o_left=True):
    p = lm.Program(); P = p.put
    XL = 4
    XR = XL + NL - 1
    RW = max(XR + 2, 14)
    SPAWN, RTOP, RT, M1, M2, M3, RB, RBOT = 1,2,3,4,5,6,7,8
    WALL_B = 9
    p.room(0, 0, RW, WALL_B+1)

    # I room side-mounted on the LEFT strip (same cols as O room, different rows) -> no top stack
    p.input_room(-5, 0)                # I at (-4,1), room cols -5..-3 rows 0..2
    p.pipe([(-2,1),(-1,1)])            # I-east -> reader west wall (0,1) at row1

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

    S = WALL_B
    for c in range(XL, XR+1):
        p.pipe([(c,S+1),(c,S+2)])

    # ---- collector: 2-col serpentine readout ----
    CN = S+3                           # 12
    # rows: ENTRY, C_RTOP, C_RT, C_M1, C_M2, C_M3, C_RB, C_RBOT
    ENTRY  = CN+1                      # 13  read count -> BP
    C_RTOP = CN+2                      # 14  top exit lane (B up-exits)
    C_RT   = CN+3                      # 15  A=v / B=d
    C_M1   = CN+4                      # 16  A=R / B=s
    C_M2   = CN+5                      # 17  m / m
    C_M3   = CN+6                      # 18  A=s / B=R
    C_RB   = CN+7                      # 19  A=d / B=^
    C_RBOT = CN+8                      # 20  bottom exit lane (A down-exits)
    CWALL  = CN+9                      # 21
    p.room(0, CN, RW, CWALL-CN+1)      # rows 12..21
    A, B = 7, 6                        # serpentine columns (A right, B left)

    # entry: read count, set BP, drop into A-top heading down
    P(1,ENTRY,">"); P(2,ENTRY,"@"); P(3,ENTRY,"r"); P(4,ENTRY,"b")
    # route east to A (col7) then down. cols5,6 on ENTRY -> '>' ; (A,ENTRY) -> 'v'
    P(5,ENTRY,">"); P(6,ENTRY,">"); P(A,ENTRY,"v")
    P(A,C_RTOP,"v")                    # passthrough top exit lane at col A (A is down-col)
    # serpentine cells
    P(A,C_RT,"v"); P(A,C_M1,"R"); P(A,C_M2,"m"); P(A,C_M3,"s"); P(A,C_RB,"d")
    P(B,C_RT,"d"); P(B,C_M1,"s"); P(B,C_M2,"m"); P(B,C_M3,"R"); P(B,C_RB,"^")
    # exit lanes: C_RTOP (B up-exit at col B -> north into here) and C_RBOT (A down-exit)
    # both run WEST to col1 corridor, up/down back to ENTRY '>'
    for c in range(2, A+1):
        if p.get(c,C_RTOP)==" ": P(c,C_RTOP,"<")
        if p.get(c,C_RBOT)==" ": P(c,C_RBOT,"<")
    # col1 corridor: from C_RBOT up to ENTRY
    for r in range(C_RTOP, C_RBOT+1):
        if p.get(1,r)==" ": P(1,r,"^")

    # count pipe -> collector top col3
    p.pipe([(-1,2),(-1,S+1),(3,S+1),(3,S+2)])

    # output room to the LEFT; single output pipe from collector west wall
    p.output_room(-5, C_M1)
    p.pipe([(-1,C_M1+1),(-2,C_M1+1)])
    return p

if __name__ == "__main__":
    NL = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    p = build(NL)
    out = "/Users/visenbaev/icfpc26/scratchpad/snake/snake6.man"
    p.save(out)
    print(p.render())
    print("footprint:", p.footprint())
