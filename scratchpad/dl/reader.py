import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

# READER test: descending east staircase writing v_i -> lane i, count-controlled.
# Verify by a trivial collector that blocking-reads lanes 0..K-1 (forward) for a FIXED small n,
# single round, and outputs them (so we see lane contents).

NLANE = 16
LB = 7
def L(i): return LB + 3*i

def build(testk):
    p = lm.Program(); P = p.put
    dc0, dr0 = 5, 3
    lastdec_row = dr0 + 2*NLANE
    RB = lastdec_row + 2
    RW = L(NLANE-1) + 4
    p.room(0, 0, RW, RB+2)                 # reader interior rows 1..RB; south wall row RB+1
    p.input_room(2, -5); p.pipe([(3,-2),(3,-1)])   # input into reader top col3 (gap rows -2,-1)
    # top: return-turn, spawn, count read, b, drop to stair0
    P(1,1,">"); P(2,1,"@"); P(3,1,"r"); P(4,1,"b"); P(5,1,"v")
    for i in range(NLANE+1):
        dc = dc0 + 3*i; dr = dr0 + 2*i
        P(dc, dr, "a")
        if i < NLANE:
            P(dc+1, dr, "r"); P(dc+2, dr, "s"); P(dc+3, dr, "v"); P(dc+3, dr+1, "m")
    # exit funnel: down each exit col to RB, west rail, up col1 -> back to ">"
    for c in range(2, RW-1):
        if p.get(c, RB) == " ": P(c, RB, "<")
    P(1, RB, "^")
    for r in range(2, RB):
        if p.get(1, r) == " ": P(1, r, "^")
    S = RB+1                               # reader south wall row

    # lanes down to collector: gap rows S+1,S+2 ; collector north wall CN=S+3
    CN = S + 3
    Rs = CN + 1
    CB = Rs + 4
    p.room(0, CN, RW, CB-CN+2)             # collector interior Rs..CB; south wall CB+1
    for i in range(NLANE):
        c = L(i); p.pipe([(c, S+1), (c, S+2)])
    CS = CB+1                              # collector south wall row
    p.output_room(2, CS+3); p.pipe([(3, CS+1),(3, CS+2)])

    # trivial collector: read lanes 0..testk-1 forward, send each to O. spawn, walk east reading.
    # place r at lane cols, s to O between. Man heading east from col LB.
    # Man @ at (LB-1, Rs) heading east. At lane col c: r; next: s.
    P(LB-1, Rs, "@")
    for i in range(testk):
        c = L(i)
        P(c, Rs, "r"); P(c+1, Rs, "s")
    P(L(testk-1)+2, Rs, "H")
    return p

if __name__ == "__main__":
    k = int(sys.argv[1]) if len(sys.argv)>1 else 3
    p = build(k)
    p.save(os.path.join(os.path.dirname(__file__), "reader.man"))
    print(p.render())
