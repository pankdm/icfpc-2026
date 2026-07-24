#!/usr/bin/env python3
"""Prototype: DRIVER + display + cmd pipe, fed by a fake SOURCE man.
Driver decodes cmd stream [addr+1,15,...,-1]."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import littleman as lm


def put(p, x, y, ch):
    assert p.get(x, y) == " ", f"overlap at {(x,y)}: {p.get(x,y)!r} vs {ch!r}"
    p.put(x, y, ch)


def hglide(p, y, x0, x1):
    """no-op; cells left blank glide. (kept for clarity)"""
    pass


def build_driver(p, dvx, dvy, cmd_attach_from):
    """Driver room top-left at (dvx,dvy). cmd_attach_from = source-side pipe start.
    Returns dict with display Rect D and driver Rect."""
    # ------- display below driver -------
    DX = dvx + 6
    DY = dvy + 30
    D = p.display(DX, DY, 34, 26)
    # ------- driver room -------
    W, H = 34, 26
    DR = p.room(dvx, dvy, W, H)
    L, T, Rr, B = DR.ix0, DR.iy0, DR.ix1, DR.iy1
    cBr = L + 8
    rENTRY = T + 13
    rSWAP = T + 2
    rRET = T
    rPIX = B
    Ca = cBr - 1        # ADDR attach col (over display top)
    Cd = L + 2          # DATA attach col (WEST of display -> down to left wall)
    Cswap = cBr + 1     # SWAP attach col (north wall)
    railW = L + 1       # west return rail column
    railR = Rr          # east return rail column

    # ---- spawn + junction ----
    put(p, L, rENTRY, "@")                 # spawn, faces east -> glides into junction
    put(p, railW, rENTRY, ">")             # junction: any arrival -> east into r

    # ---- read / branch ----
    put(p, cBr - 1, rENTRY, "r")           # read cmd  (col Ca==cBr-1 ADDR is a diff row; r=cmd anyway)
    put(p, cBr, rENTRY, "X")               # east: A>0 CW=south(pixel); A<0 CCW=north(swap)

    # ---- PIXEL branch (south down col cBr, then WEST along bottom row) ----
    put(p, cBr, rENTRY + 1, "M")
    put(p, cBr, rENTRY + 2, "1")
    put(p, cBr, rENTRY + 3, "-")
    put(p, cBr, rENTRY + 4, "N")           # A = v-1
    put(p, cBr, rPIX, "<")                 # reach bottom row, turn WEST
    put(p, Ca, rPIX, "s")                  # ADDR send (col Ca, south wall)
    put(p, Ca - 1, rPIX, "r")              # read color
    put(p, Cd, rPIX, "s")                  # DATA send (col Cd, south wall -> west of display)
    put(p, railW, rPIX, "^")               # up the WEST rail to junction

    # ---- SWAP branch (north up col cBr, then EAST) ----
    put(p, cBr, rENTRY - 1, "0")           # A=0
    put(p, cBr, rSWAP, ">")                # reach near-top row, turn east
    put(p, Cswap, rSWAP, "s")              # SWAP send (north wall)
    put(p, railR, rSWAP, "^")              # up east rail
    put(p, railR, rRET, "<")               # top, west
    put(p, railW, rRET, "v")               # down west rail into junction

    # ---- pipes ----
    # ADDR: south wall col Ca -> display top (short)
    p.pipe([(Ca, DR.y1 + 1), (Ca, D.y0 - 1)])
    # DATA: south wall col Cd (west of display) -> down -> display LEFT wall
    dRow = D.iy0 + 4
    p.pipe([(Cd, DR.y1 + 1), (Cd, dRow), (D.x0 - 1, dRow)])
    # SWAP: north wall col Cswap -> around right -> display BOTTOM wall (long)
    sBcol = DX + 17
    p.pipe([(Cswap, DR.y0 - 1), (Cswap, DR.y0 - 3), (D.x1 + 3, DR.y0 - 3),
            (D.x1 + 3, D.y1 + 5), (sBcol, D.y1 + 5), (sBcol, D.y1 + 1)])
    # cmd: from source -> driver WEST wall at rENTRY (straight horizontal)
    if cmd_attach_from is not None:
        p.pipe([cmd_attach_from, (DR.x0 - 1, rENTRY)])
    return {"D": D, "DR": DR, "rENTRY": rENTRY}


def build(cmd_values):
    p = lm.Program()
    dvx, dvy = 32, 4
    rENTRY = (dvy + 1) + 13
    # fake source room to the west of driver, emit row aligned to rENTRY
    src = p.room(0, rENTRY - 1, 28, 7)
    sx0, sy0 = src.ix0, src.iy0
    put(p, sx0, sy0, "@")
    cur = sx0 + 1
    for v in cmd_values:
        if v < 0:
            put(p, cur, sy0, "1"); cur += 1
            put(p, cur, sy0, "N"); cur += 1
        elif v < 10:
            put(p, cur, sy0, str(v)); cur += 1
        else:
            for ch in "`%d`" % v:
                put(p, cur, sy0, ch); cur += 1
        put(p, cur, sy0, "s"); cur += 1
    put(p, cur, sy0, "H")
    info = build_driver(p, dvx, dvy, (src.x1 + 1, sy0))
    return p


if __name__ == "__main__":
    import json
    p = build([170, 15, -1])            # pixel (9,5): addr 169
    path = os.path.join(os.path.dirname(__file__), "proto.man")
    p.save(path)
    print("saved", path, "footprint", p.footprint())
    print(json.dumps(p.grade("plotter")))
