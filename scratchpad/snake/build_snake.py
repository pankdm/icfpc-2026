import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "icfpc26", "tools"))
sys.path.insert(0, _REPO + "/tools")
import littleman as lm

# SERPENTINE SNAKE reverse-a-list.
#  READER: reads n -> BP=n, B=n. Travels east to rightmost lane XR, weaves WEST
#   through n lanes (pitch-1). Each lane: r(input) -> m(BP--) -> s(to that lane's
#   down-pipe). Exits (straight) when BP==0. Weaving stores v1->XR, v2->XR-1, ...
#   so filled lanes are the RIGHTMOST n; leftmost-filled holds v_n.
#  COLLECTOR: waits for count n (sent by reader AFTER all fills = barrier), then does
#   n * (R -> s). R pulls the leftmost READY incoming pipe = leftmost-filled = v_n,
#   then v_{n-1}, ... = reversed. Loops for next round.

def build(NL=16):
    p = lm.Program(); P = p.put
    XL = 5
    XR = XL + NL - 1
    # reader interior rows
    Rf, Rtop, RT, M1, M2, M3, RB, Rbot = 1,2,3,4,5,6,7,8
    RW = XR + 3               # reader room width (x=0..RW-1)
    p.room(0, 0, RW, Rbot+2)  # walls row 0 and Rbot+1=9; interior 1..8

    # input room + pipe into reader top near spawn (col 2)
    p.input_room(0, -4)              # I at cols 0-2, rows -4..-2
    p.pipe([(1, -1), (1, 0)])        # from I-room bottom (0,-2..) down to reader top wall col1
    # spawn + preamble on Rf
    P(1, Rf, "@"); P(2, Rf, "r"); P(3, Rf, "M"); P(4, Rf, "b")
    # feeder east along Rf to XR (empty cells = nop, continue east)
    P(XR, Rf, "v")                   # at rightmost, turn south to descend
    P(XR, Rtop, "v")                 # pass-through Rtop (down-lane col, exit-lane unused here)

    # per-lane cells, j = XR-c (0=rightmost=down)
    for c in range(XL, XR+1):
        j = XR - c
        if j % 2 == 0:  # down-lane
            P(c, RT, "v"); P(c, M1, "r"); P(c, M2, "m"); P(c, M3, "s"); P(c, RB, "d")
        else:           # up-lane
            P(c, RT, "a"); P(c, M1, "s"); P(c, M2, "m"); P(c, M3, "r"); P(c, RB, "^")
    # exit lanes: Rtop (up exits) and Rbot (down exits) run WEST
    for c in range(XL, XR+1):
        if p.get(c, Rtop) == " ": P(c, Rtop, "<")
        if p.get(c, Rbot) == " ": P(c, Rbot, "<")

    # column down-pipes: reader bottom wall (row Rbot+1) col c -> down 2 cells
    S = Rbot + 1                     # reader south wall row
    for c in range(XL, XR+1):
        p.pipe([(c, S+1), (c, S+2)])

    # ---- converge exit lanes to a loop that (1) sends count n, (2) returns to spawn r
    # Rtop west end -> col1 up to Rf spawn ; Rbot west end -> col1 up too.
    # bring both to col XL-1 then to a count-send cell then back to spawn.
    LX = XL - 1                      # convergence column (=4? no, 4 is 'b'). use LX2
    # route Rtop: from (XL,Rtop) already '<' to (1,Rtop); then need to reach spawn r at (2,Rf)
    # We'll route both lanes to (1, Rtop) and (1, Rbot), up/down to a count room, then to spawn.
    # Simpler: send count from a dedicated cell reached by both. Put count-send at (1, mid).
    # Rtop lane: (XL..1, Rtop) all '<' ; at (1,Rtop) go... need south to reach count cell.
    # Let's make col 1 a vertical corridor connecting Rtop..Rbot, with a count-send + loop.
    # clear the wall? no. Use interior col 1.
    # (1,Rtop): turn down; (1,Rbot): turn up; meet at (1, M2) where we send count then go to spawn.
    P(1, Rtop, "v")
    P(1, Rbot, "^")
    # corridor col1 rows Rtop..Rbot: put W (swap A,B -> A=n) then s(count) then '^' to spawn
    P(1, M1, "W")     # A <-> B  => A = n (saved in B), B = last value
    P(1, M2, "s")     # send count to nearest outgoing pipe (count pipe, placed nearest here)
    P(1, M3, "^")
    # from (1,M1) after W heading? need path Rtop->down->W->s->up->spawn. Let's lay col1:
    # (1,Rf)=@ spawn. (1,Rtop)=v down. (1,RT)=? (1,M1)=W (1,M2)=s (1,M3)=^ up ... conflict.
    # Simplify below in v2. For now leave; will fix after tracing.

    # count pipe: from reader col1 (near M2) out to collector. Put outgoing on WEST wall.
    p.pipe([(-1, M2), (-2, M2), (-2, S+6), (-1, S+6)])   # placeholder route to collector west

    # ---- COLLECTOR room below ----
    CN = S + 3                       # collector north wall row
    Ci = CN + 1                      # interior row
    CB = CN + 4
    p.room(0, CN, RW, CB-CN+1)
    # column pipes continue from (c,S+2) into collector top wall (c, CN)
    for c in range(XL, XR+1):
        p.pipe([(c, S+2+1), (c, CN)])  # from just below reader-south into collector-north

    P(2, Ci, "@")
    # collector: read count -> BP, then loop R,s,m until BP==0, then re-read count
    # placeholder simple version; refine after trace
    P(2, Ci, "@"); P(3, Ci, "r"); P(4, Ci, "b")
    # output room + pipe
    p.output_room(0, CB+2)
    p.pipe([(1, CB), (1, CB+1)])
    return p

if __name__ == "__main__":
    NL = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    p = build(NL)
    out = os.path.join(os.path.dirname(__file__), "snake_wip.man")
    p.save(out)
    print(p.render())
    print("footprint:", p.footprint())
