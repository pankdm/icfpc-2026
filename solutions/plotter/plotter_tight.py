#!/usr/bin/env python3
"""Layout-fold variant of plotter-25m: op-multiset IDENTICAL (private-safe).
Only the DRIVER/display geometry changes (pipe cells / placement):
  * display inset DX = dvx+5 (was dvx+6): saves 1 col (Cd stays west of display).
  * SWAP bulge D.x1+2 (was +3): saves 1 col on the far-right descent.
Then rebalance band_right for the new square/score optimum.
Champion plotter-25m.man is left untouched.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import littleman as lm
import plotter_planC as PC
import plotter_25m as M


def tight_build_driver(p, dvx, dvy, cmd_attach_from):
    def put(x, y, ch):
        assert p.get(x, y) == " ", f"overlap at {(x,y)}: {p.get(x,y)!r} vs {ch!r}"
        p.put(x, y, ch)
    DX = dvx + 5                       # was +6
    DY = dvy + 30
    D = p.display(DX, DY, 34, 26)
    W, H = 34, 26
    DR = p.room(dvx, dvy, W, H)
    L, T, Rr, B = DR.ix0, DR.iy0, DR.ix1, DR.iy1
    cBr = L + 8
    rENTRY = T + 13
    rSWAP = T + 2
    rRET = T
    rPIX = B
    Ca = cBr - 1
    Cd = L + 2
    Cswap = cBr + 1
    railW = L + 1
    railR = Rr
    put(L, rENTRY, "@")
    put(railW, rENTRY, ">")
    put(cBr - 1, rENTRY, "r")
    put(cBr, rENTRY, "X")
    put(cBr, rENTRY + 1, "M")
    put(cBr, rENTRY + 2, "1")
    put(cBr, rENTRY + 3, "-")
    put(cBr, rENTRY + 4, "N")
    put(cBr, rPIX, "<")
    put(Ca, rPIX, "s")
    put(Ca - 1, rPIX, "r")
    put(Cd, rPIX, "s")
    put(railW, rPIX, "^")
    put(cBr, rENTRY - 1, "0")
    put(cBr, rSWAP, ">")
    put(Cswap, rSWAP, "s")
    put(railR, rSWAP, "^")
    put(railR, rRET, "<")
    put(railW, rRET, "v")
    # ADDR
    p.pipe([(Ca, DR.y1 + 1), (Ca, D.y0 - 1)])
    # DATA
    dRow = D.iy0 + 4
    p.pipe([(Cd, DR.y1 + 1), (Cd, dRow), (D.x0 - 1, dRow)])
    # SWAP: bulge reduced from +3 to +2
    sBcol = DX + 17
    p.pipe([(Cswap, DR.y0 - 1), (Cswap, DR.y0 - 3), (D.x1 + 2, DR.y0 - 3),
            (D.x1 + 2, D.y1 + 5), (sBcol, D.y1 + 5), (sBcol, D.y1 + 1)])
    if cmd_attach_from is not None:
        p.pipe([cmd_attach_from, (DR.x0 - 1, rENTRY)])
    return {"D": D, "DR": DR, "rENTRY": rENTRY}


def build(band_right=30):
    _orig = PC.build_driver
    PC.build_driver = tight_build_driver
    try:
        p = M.build(band_right)
    finally:
        PC.build_driver = _orig
    return p


if __name__ == "__main__":
    import subprocess, re
    HERE = os.path.dirname(__file__)
    for br in [28, 29, 30, 31, 32]:
        p = build(br)
        w, h, box = p.footprint()
        tmp = os.path.join(HERE, "_tight_br%d.man" % br)
        p.save(tmp)
        r = subprocess.run(["node", os.path.join(HERE, "..", "..", "tools", "grade.js"), "plotter", tmp],
                           capture_output=True, text=True)
        m = re.search(r"(\d+)/(\d+) public", r.stdout)
        passed = m.group(0) if m else "?"
        m2 = re.search(r"box (\d+)\s+avgTicks ([\d.]+)\s+SCORE (\d+)", r.stdout)
        sc = m2.groups() if m2 else ("?", "?", "?")
        print("br=%d %s w=%d h=%d box=%d avgTicks=%s score=%s" % (br, passed, w, h, box, sc[1], sc[2]))
        os.remove(tmp)
