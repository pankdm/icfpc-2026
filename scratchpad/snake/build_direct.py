import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import os, sys
sys.path.insert(0, _REPO + "/tools")
import littleman as lm

# TEST: reader fills NL lanes right-aligned; lane pipes feed O ROOM DIRECTLY (no collector).
# Question: does O accept NL incoming pipes, and does it emit reading-order (leftmost first)?
def build(NL=3, owide=None):
    p = lm.Program(); P = p.put
    XL = 5
    XR = XL + NL - 1
    RW = XR + 3
    Rf, Rtop, RT, M1, M2, M3, RB, Rbot = 1,2,3,4,5,6,7,8
    p.room(0, 0, RW, Rbot+2)
    p.input_room(0, -5)
    p.pipe([(1, -2), (1, -1)])
    P(1, Rf, "@"); P(2, Rf, "r"); P(3, Rf, "b")
    P(XR, Rf, "v"); P(XR, Rtop, "v")
    for c in range(XL, XR+1):
        j = XR - c
        if j % 2 == 0:
            P(c, RT, "v"); P(c, M1, "r"); P(c, M2, "m"); P(c, M3, "s"); P(c, RB, "d")
        else:
            P(c, RT, "a"); P(c, M1, "s"); P(c, M2, "m"); P(c, M3, "r"); P(c, RB, "^")
    for c in range(XL, XR+1):
        if p.get(c, Rtop) == " ": P(c, Rtop, "<")
        if p.get(c, Rbot) == " ": P(c, Rbot, "<")
    P(1, Rtop, "H"); P(1, Rbot, "H")
    # idle man (3x3 clockwise loop, never halts) to keep the sim ticking so pipes drain
    a, b = RW+2, 1
    p.room(RW+1, 0, 5, 5)
    P(a,b,">"); P(a+1,b,"@"); P(a+2,b,"v")
    P(a+2,b+1,"v"); P(a+2,b+2,"<"); P(a+1,b+2,"<"); P(a,b+2,"^"); P(a,b+1,"^")
    S = Rbot + 1                        # reader south wall
    # O room: wide enough to have NL non-corner top-wall cells at cols XL..XR
    ox0 = XL - 1                        # O left wall col
    ow = NL + 2                         # width -> non-corner top cols XL..XR
    oy = S + 3                          # O top wall row
    p.room(ox0, oy, ow, 3)
    P(ox0 + 1, oy+1, "O")              # single O in interior
    # lane pipes: reader-south (c,S) -> down -> O top (c,oy)
    for c in range(XL, XR+1):
        p.pipe([(c, S+1), (c, S+2)])   # ends (c,S+2); O top wall must be at (c,S+3)=oy
    return p

if __name__ == "__main__":
    NL = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    p = build(NL)
    out = _REPO + "/scratchpad/snake/direct.man"
    p.save(out)
    print(p.render())
    print("footprint:", p.footprint())
