import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import os, sys
sys.path.insert(0, _REPO + "/tools")
import littleman as lm

# Reader ONLY: read n -> BP=n, weave WEST filling column pipes, then halt.
def build(NL=3):
    p = lm.Program(); P = p.put
    XL = 5
    XR = XL + NL - 1
    Rf, Rtop, RT, M1, M2, M3, RB, Rbot = 1,2,3,4,5,6,7,8
    RW = XR + 3
    p.room(0, 0, RW, Rbot+2)          # interior rows 1..8
    p.input_room(0, -5)               # I room rows -5..-3
    p.pipe([(1, -2), (1, -1)])        # pipe cells above reader top wall (row0)
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
    # exit lanes to a halt: send them west to col 1 then H
    P(1, Rtop, "H"); P(1, Rbot, "H")
    S = Rbot + 1                       # reader south wall row (=9)
    p.room(0, S+3, RW, 4)              # buffer room top wall at S+3
    for c in range(XL, XR+1):
        p.pipe([(c, S+1), (c, S+2)])   # reader-south (c,S) -> buffer-top (c,S+3)
    return p

if __name__ == "__main__":
    NL = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    p = build(NL)
    out = _REPO + "/scratchpad/snake/reader_only.man"
    p.save(out)
    print(p.render())
    print("footprint:", p.footprint())
