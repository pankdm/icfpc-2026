import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

# Barrier-synchronized delay-line reverse (Design 2), full multi-round.
NLANE = 16
LB = 7
def L(i): return LB + 3*i

def build():
    p = lm.Program(); P = p.put
    # ---------------- READER ----------------
    dc0, dr0 = 5, 3
    RB = dr0 + 2*NLANE + 2
    RW = L(NLANE-1) + 4
    p.room(0, 0, RW, RB+2)                     # reader interior 1..RB, south wall RB+1
    p.input_room(2, -5); p.pipe([(3,-2),(3,-1)])
    P(1,1,">"); P(2,1,"@"); P(3,1,"r"); P(4,1,"b"); P(5,1,"v")
    for i in range(NLANE+1):
        dc = dc0 + 3*i; dr = dr0 + 2*i
        P(dc, dr, "a")
        if i < NLANE:
            P(dc+1, dr, "r"); P(dc+2, dr, "s"); P(dc+3, dr, "v"); P(dc+3, dr+1, "m")
    for c in range(2, RW-1):
        if p.get(c, RB) == " ": P(c, RB, "<")
    P(1, RB, "^")
    for r in range(2, RB):
        if p.get(1, r) == " ": P(1, r, "^")
    P(1, RB-1, "s")                            # send DONE pulse to west done-pipe
    S = RB + 1                                 # reader south wall

    # ---------------- COLLECTOR ----------------
    CN = S + 3                                 # collector north wall
    Re = CN + 1                                # entry row
    Rs = CN + 2                                # scan row
    CB = Rs + 5                                # bottom rail
    p.room(0, CN, RW, CB - CN + 2)             # interior Re..CB, south wall CB+1
    for i in range(NLANE):
        c = L(i); p.pipe([(c, S+1), (c, S+2)])
    CS = CB + 1
    p.output_room(2, CS+3); p.pipe([(3, CS+1), (3, CS+2)])

    # done-pipe: reader west wall (0,RB-1) -> west side -> collector west wall (0,Re)
    p.pipe([(-1, RB-1), (-2, RB-1), (-2, Re), (-1, Re)])

    # entry: (1,Re)='>' reset-turn, (2,Re)=@, (3,Re)=r barrier, east-walk to L15+2, drop to scan
    P(1, Re, ">"); P(2, Re, "@"); P(3, Re, "r")
    east_end = L(NLANE-1) + 2
    P(east_end, Re, "v")                       # drop to scan
    P(east_end, Rs, "<")                       # face west
    # scan units lanes 15..0
    for i in range(NLANE-1, -1, -1):
        c = L(i)
        P(c, Rs, "q")
        P(c-1, Rs, "a")
        P(c-2, Rs, "<")
        P(c-1, Rs+1, "r"); P(c-1, Rs+2, "s"); P(c-1, Rs+3, "<")
        P(c-2, Rs+1, "^"); P(c-2, Rs+2, "^"); P(c-2, Rs+3, "^")
    # fixed west stop at col LB-3
    P(LB-3, Rs, "v")
    # collector reset: down col LB-3 to CB, west rail to col1, up col1 to Re
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
    p.save(os.path.join(os.path.dirname(__file__), "flat.man"))
    print(p.render())
    print("footprint:", p.footprint())
