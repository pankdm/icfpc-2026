import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

# FLAT COMB reverse-a-list.
#   READER  : flat east-walking comb. Per lane: q(input count, pos-independent) ->
#             d(dive S if bp>0) -> r(read input) -> s(send to lane i) -> return up,
#             continue east. When input empty (q==0) man sails east to reset. No count,
#             no descent: relies on position-independent reads (the confirmed result).
#   COLLECTOR: flat west-walking comb (from delayline-flat, proven). Per lane 15..0:
#             q(lane count) -> a(dive if written) -> r,s to O. Skips empty lanes -> homing.
#   BARRIER : reader sends a DONE pulse on a west done-pipe once input drains; collector
#             blocks on it before sweeping (so it never races ahead of the writes).
NLANE = 16
LB = 7
def L(i): return LB + 3*i          # lane i column

def build():
    p = lm.Program(); P = p.put

    # ---------------- READER (flat east comb; mirror of the collector gadget) --------
    RRs = 2                          # reader scan row
    RRb = RRs + 5                    # reader south wall row (dive uses RRs+1..+3, +4 rail)
    RW = L(NLANE-1) + 5
    p.room(0, 0, RW, RRb+1)          # interior rows 1..RRb
    # input room + pipe into reader top (col 3, well east of the reset rail)
    p.input_room(2, -5); p.pipe([(3,-2),(3,-1)])
    # start: '>' reorient (reset lands here), @ spawn, r discards the count, then east.
    P(1, RRs, ">"); P(2, RRs, "@"); P(3, RRs, "r")
    # per-lane gadget (pitch 3), i=0..NLANE-1
    for i in range(NLANE):
        c = L(i)
        P(c,   RRs, "q")             # bp = input pipe count (single input -> pos-independent)
        P(c+1, RRs, "d")             # bp>0 -> CW (E->S) dive col c+1; else straight east (exit)
        P(c+2, RRs, ">")            # climb-top reorient east (distinct from next q@c+3)
        P(c+1, RRs+1, "r")           # read next input value
        P(c+1, RRs+2, "s")           # send to lane i (nearest lane = col c)
        P(c+1, RRs+3, ">")           # head east along dive-bottom
        P(c+2, RRs+1, "^"); P(c+2, RRs+2, "^"); P(c+2, RRs+3, "^")  # climb col c+2
    # exit rail (bp hits 0 -> man sails east): turn south, west along bottom, up col1.
    for c in range(3, RW-1):
        if p.get(c, RRs) == " ": P(c, RRs, ">")
    P(RW-2, RRs, "v")
    for r in range(RRs+1, RRb-1):                       # down rail, stop above south wall
        if p.get(RW-2, r) == " ": P(RW-2, r, "v")
    P(RW-2, RRb-1, "<")                                 # SE corner: turn west
    for c in range(2, RW-2):
        if p.get(c, RRb-1) == " ": P(c, RRb-1, "<")
    P(1, RRb-1, "^")                                    # SW corner: turn north
    for r in range(RRs+1, RRb-1):
        if p.get(1, r) == " ": P(1, r, "^")
    # DONE pulse: an s on the col1 up-rail (nearest outgoing = the west done-pipe).
    P(1, RRs+1, "s")
    S = RRb                          # reader south wall row

    # ---------------- COLLECTOR (flat west comb; from delayline-flat) ----------------
    CN = S + 3                       # collector north wall
    Re = CN + 1                      # entry row
    Rs = CN + 2                      # scan row
    CB = Rs + 5                      # bottom rail
    p.room(0, CN, RW, CB - CN + 2)
    for i in range(NLANE):
        c = L(i); p.pipe([(c, S+1), (c, S+2)])   # lane pipes reader-south -> collector-north
    CS = CB + 1
    p.output_room(1, CS+3); p.pipe([(2, CS+1), (2, CS+2)])

    # done-pipe: reader west wall (0,RRs+1) -> around west -> collector west wall (0,Re)
    p.pipe([(-1, RRs+1), (-2, RRs+1), (-2, Re), (-1, Re)])

    P(1, Re, ">"); P(2, Re, "@"); P(3, Re, "r")   # barrier: wait for DONE pulse
    east_end = L(NLANE-1) + 2
    P(east_end, Re, "v")
    P(east_end, Rs, "<")
    for i in range(NLANE-1, -1, -1):
        c = L(i)
        P(c, Rs, "q")
        P(c-1, Rs, "a")
        P(c-2, Rs, "<")
        P(c-1, Rs+1, "r"); P(c-1, Rs+2, "s"); P(c-1, Rs+3, "<")
        P(c-2, Rs+1, "^"); P(c-2, Rs+2, "^"); P(c-2, Rs+3, "^")
    P(LB-3, Rs, "v")
    for r in range(Rs+1, CB):
        if p.get(LB-3, r) == " ": P(LB-3, r, "v")
    for c in range(2, LB-2):
        if p.get(c, CB) == " ": P(c, CB, "<")
    P(1, CB, "^")
    for r in range(Re+1, CB):
        if p.get(1, r) == " ": P(1, r, "^")
    return p

if __name__ == "__main__":
    p = build()
    p.save(os.path.join(os.path.dirname(__file__), "comb.man"))
    print(p.render())
    print("footprint:", p.footprint())
