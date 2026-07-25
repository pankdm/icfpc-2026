import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import os, sys
sys.path.insert(0, _REPO + "/tools")
import littleman as lm

# Snake v5 (coordinator reconfiguration):
#  1. INPUT room on TOP touching the reader.
#  2. COUNT signal rerouted: count-send s@(3,SPAWN) attaches to a count pipe at reader-SOUTH
#     col3 (dist 8 beats lanes at dist 9), so it drops STRAIGHT down col3 -> NO left col-bulge.
#  3. READOUT = racetrack (sideways/horizontal).
#  4. OUTPUT placement selectable: 'below' (in height), 'east' (in width).
def build(NL=16, o="below"):
    p = lm.Program(); P = p.put
    XL = 4
    XR = XL + NL - 1
    RW = max(XR + 2, 14)
    SPAWN, RTOP, RT, M1, M2, M3, RB, RBOT = 1,2,3,4,5,6,7,8
    WALL_B = 9
    p.room(0, 0, RW, WALL_B+1)
    p.input_room(4, -5)
    p.pipe([(5,-2),(5,-1)])
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
    # count pipe STRAIGHT down col3 (no left bulge)
    p.pipe([(3,S+1),(3,S+2)])
    CN = S+3
    Ci = CN+1
    p.room(0, CN, RW, 5)
    P(1,Ci,">"); P(2,Ci,"@"); P(3,Ci,"r"); P(4,Ci,"b"); P(5,Ci,">")
    P(6,Ci,"R"); P(7,Ci,"s"); P(8,Ci,"m"); P(9,Ci,"d")
    P(9,Ci+1,"<"); P(8,Ci+1,"<"); P(7,Ci+1,"<"); P(6,Ci+1,"<"); P(5,Ci+1,"^")
    P(10,Ci,"v"); P(10,Ci+1,"v")
    for c in range(1,11):
        if p.get(c,Ci+2)==" ": P(c,Ci+2,"<")
    P(1,Ci+2,"^"); P(1,Ci+1,"^")
    CB = CN+4
    if o == "below":
        p.output_room(0, CB+3); p.pipe([(1,CB+1),(1,CB+2)])
    elif o == "east":
        p.output_room(RW+2, Ci); p.pipe([(RW,Ci+1),(RW+1,Ci+1)])
    return p

if __name__ == "__main__":
    NL = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    o = sys.argv[2] if len(sys.argv) > 2 else "below"
    p = build(NL, o)
    out = _REPO + "/scratchpad/snake/snake5.man"
    p.save(out)
    print(p.render()); print("footprint:", p.footprint())
