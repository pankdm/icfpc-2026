#!/usr/bin/env python3
"""build_lane.py -- the LLLM interpreter on the hand-structured LANE floorplan.

See build_micro.py for the design contract and micro_core / micro_asm for the
machinery.  This file is the program.

DATA
  PROG ring   32 slots: C0,V0,C1,V1,...,C15,V15 -- two 4-bit planes, one 64-bit
              word per LLLM row.  Kept in CANONICAL order at every block
              boundary, so row y is addressed by rotating 2y, reading, and
              rotating the remaining 30-2y: exactly 32 pops per tick, no decode
              and no 16-way branch.
  STATE ring  9 named slots, head tracked at emit time.
  SCRATCH     a short ring used as a named temp file (only B survives a rotation,
              so every 3-operand expression goes through it).

CLASSIFIER  h(c) = ((c*29) >> 6) & 15 is injective over the twelve non-digit
            characters; two packed nibble tables give colour and operand.  Digits
            are split off by ONE branch on (9-t)*t >= 0.

WALLS       resolved POSITIONALLY, never by character ('swan dive' has a real '+'
            and '-' inside the room).  A row is a WALL row iff its colour word
            contains no nibble 4, i.e. no '|':
                a = C & M4 ; b = (C>>1) & M4 ; h = (a&b)^a
            h == 0  =>  wall row  =>  C := b   (every non-space nibble -> 4)
            That is exact: interior rows always carry the room's two '|', rows
            outside the room are all spaces (h == 0, and b == 0, a no-op).

DISPLAY     one driver pipe carries the whole protocol:
                v >= 0  -> DATA v      v == -1 -> SWAP 0      v <= -2 -> ADDR -v-2
            A frame is 256 DATA + ADDR(man) + DATA 9 + SWAP.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))

import micro_core as mc                                    # noqa: E402
from micro_asm import Asm, Ring, Scratch, konst_tokens     # noqa: E402

COLW = 900518012169219          # colour nibble per hash slot
VALW = 334255563538446          # operand nibble per hash slot
DXT = 289                       # nibble[dir] = dx+1   (N,E,S,W)
DYT = 4624                      # nibble[dir] = dy+1

LOAD_SLOTS = ["col", "val", "cw", "vw", "n", "mani", "W", "H", "m4",
               "COLW", "VALW"]
STEP_SLOTS = ["halted", "k", "x", "y", "dir", "A_lm", "B_lm", "val"]


def build(CW=104, CY0=20, CBOT=900, save_to=None, verbose=False):
    g = mc.geometry(CW=CW, CY0=CY0, CBOT=CBOT)
    win = mc.lane_windows(g)
    L, caps = mc.build_shell(g)
    freecols = [c for c in range(g["IXLO"], g["IXHI"] + 1) if c % 4 in (0, 1)]
    wrapcols = {freecols[0], freecols[1], freecols[-1], freecols[-2]}
    forbidden = ([c for c in range(g["IXLO"], g["IXHI"] + 1) if c % 4 in (2, 3)]
                 + sorted(wrapcols))
    E = mc.Emit(L, g, win, forbidden, wrapcols=wrapcols)
    A = Asm(L, E, g, [c for c in forbidden if c not in wrapcols])
    S = Ring(A, "S", LOAD_SLOTS)
    T = Scratch(A, "T", 9)
    A.S, A.T = S, T
    K, op = A.konst, A.op
    tok = E.tok

    # ═══ LOAD: read W*H characters into the two planes ═══════════════════
    A.loop("LOADHEAD", "LOADBODY", "PADSET")

    A.block("LOADBODY")
    op("m")
    tok("r:I")                                   # A = c
    T.push("cA"); T.push("cB"); T.push("cC")
    K(48); op("M")
    T.pop("cA"); op("-")                         # A = t = c - 48
    T.push("tA"); T.push("tB")
    op("M"); op("9"); op("-"); op("*")           # A = (9-t)*t  >= 0 iff digit
    A.branch("X", up="NONDIG", down="DIGIT", straight="DIGIT")

    A.block("DIGIT")
    T.drop("cB"); T.drop("tB")
    S.get("col"); K(8); S.put()
    S.get("val"); T.pop("tA"); S.put()
    S.home()
    A.jump("ATTEST")
    A.endblock()

    A.block("NONDIG")
    T.drop("tA"); T.drop("tB")
    K(29); op("M")
    T.pop("cB"); op("*")                         # A = 29c
    T.push("h"); K(6); op("M"); T.pop("h"); op("}")
    T.push("h"); K(15); op("M"); T.pop("h"); op("&")     # A = hash slot
    T.push("hA"); T.push("hB")
    K(4); op("M"); T.pop("hA"); op("*"); T.push("shA")
    K(4); op("M"); T.pop("hB"); op("*"); T.push("shB")
    S.get("COLW"); T.push("tw"); S.put()
    T.pop("shA"); op("M"); T.pop("tw"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    T.push("colv")
    S.get("VALW"); T.push("tw"); S.put()
    T.pop("shB"); op("M"); T.pop("tw"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    T.push("valv")
    S.get("col"); T.pop("colv"); S.put()
    S.get("val"); T.pop("valv"); S.put()
    S.home()
    A.jump("ATTEST")
    A.endblock()

    A.block("ATTEST")
    K(64); op("M")
    T.pop("cC"); op("-")                         # A = z = c - 64
    op("M"); op("N"); op("|")                    # A = (-z) | z
    T.push("z"); K(63); op("M"); T.pop("z"); op("}")
    op("M"); op("1"); op("+")                    # A = 1 + (-1|0)  -> 1 iff '@'
    T.push("is")
    S.get("col"); T.push("cv"); S.put()
    S.get("val"); T.push("vv"); S.put()
    K(16); op("M"); S.get("cw"); op("*")         # A = 16*cw
    T.push("t"); T.pop("cv"); op("M"); T.pop("t"); op("+")
    S.put()
    K(16); op("M"); S.get("vw"); op("*")
    T.push("t"); T.pop("vv"); op("M"); T.pop("t"); op("+")
    S.put()
    S.get("n"); T.push("n1")
    op("M"); op("1"); op("+")                    # A = n+1
    T.push("np")
    S.put()
    T.pop("is"); op("M"); T.pop("n1"); op("*")   # A = is * n
    op("M"); S.get("mani"); op("+"); S.put()
    S.get("W"); T.push("w"); S.put()
    T.pop("w"); op("M"); T.pop("np"); op("%")    # A = (n+1) % W
    T.push("re")
    S.home()
    T.pop("re")
    A.branch("X", up="HALTBLK", down="LOADHEAD", straight="ROWEND")

    A.block("ROWEND")
    K(64); T.push("c64")
    S.get("W"); T.push("w"); S.put()
    T.pop("w"); op("M"); op("4"); op("*"); op("M")
    T.pop("c64"); op("-")                        # A = 64 - 4W
    T.push("shA"); T.push("shB")
    T.pop("shA"); op("M")
    S.get("cw"); op("{"); tok("s:P"); op("0"); S.put()
    T.pop("shB"); op("M")
    S.get("vw"); op("{"); tok("s:P"); op("0"); S.put()
    S.home()
    A.jump("LOADHEAD")
    A.endblock()

    # ═══ PAD the plane to 16 rows ════════════════════════════════════════
    A.block("PADSET")
    K(16); T.push("c16")
    S.get("H"); T.push("h1"); S.put()
    T.pop("h1"); op("M"); T.pop("c16"); op("-")  # A = 16 - H
    op("b")
    S.home()
    A.jump("PADHEAD")
    A.endblock()

    A.loop("PADHEAD", "PADBODY", "FIXSET")
    A.block("PADBODY")
    op("m"); op("0"); tok("s:P"); tok("s:P")
    A.jump("PADHEAD")
    A.endblock()

    # ═══ WALL PASS: recolour the room's horizontal walls ═════════════════
    A.block("FIXSET")
    K(16); op("b")
    S.home()
    A.jump("FIXHEAD")
    A.endblock()

    A.loop("FIXHEAD", "FIXBODY", "STEPSET")

    A.block("FIXBODY")
    op("m")
    tok("r:P")                                   # A = C[row]
    T.push("C1"); T.push("C2"); T.push("C3")
    op("1"); op("M"); T.pop("C1"); op("}")       # A = C>>1
    T.push("s")
    S.get("m4"); T.push("m4c"); S.put(); S.home()
    T.pop("m4c"); op("M")                        # B = 0x4444...
    T.pop("C2"); op("&"); T.push("a")            # a = C & M4
    T.pop("s"); op("&")                          # b = (C>>1) & M4
    T.push("b1"); T.push("b2")
    T.pop("a"); op("M")
    T.pop("b1"); op("&"); op("~")                # h = (a&b) ^ a
    A.branch("X", up="HALTBLK", down="FIXNORM", straight="FIXWALL")

    A.block("FIXWALL")
    T.drop("C3"); T.pop("b2")
    A.jump("FIXJOIN")
    A.endblock()

    A.block("FIXNORM")
    T.drop("b2"); T.pop("C3")
    A.jump("FIXJOIN")
    A.endblock()

    A.block("FIXJOIN")
    tok("s:P"); tok("r:P"); tok("s:P")
    A.jump("FIXHEAD")
    A.endblock()

    # ═══ hand the ring over to the STEP schema ═══════════════════════════
    A.block("STEPSET")
    S.get("mani"); T.push("mani"); S.put()
    S.get("W"); T.push("Wc"); S.put()
    S.home()
    for _ in range(len(LOAD_SLOTS)):
        tok("r:S")
    T.pop("Wc"); op("M")
    T.pop("mani"); op("/")                       # A = many, B = manx
    T.push("many"); op("W"); T.push("manx")
    op("0"); tok("s:S")                          # halted
    op("0"); tok("s:S")                          # k
    T.pop("manx"); tok("s:S")                    # x
    T.pop("many"); tok("s:S")                    # y
    op("1"); tok("s:S")                          # dir = EAST
    op("0"); tok("s:S")                          # A_lm
    op("0"); tok("s:S")                          # B_lm
    op("0"); tok("s:S")                          # val
    S2 = Ring(A, "S", STEP_SLOTS)
    A.S = S = S2
    A.jump("FRAME")
    A.endblock()

    # ═══ FRAME: repaint all 256 pixels, draw the man, commit ═════════════
    A.block("FRAME")
    K(16); T.push("rowc")
    A.jump("PAINTOUT")
    A.endblock()

    A.block("PAINTOUT")
    T.pop("rowc"); T.push("cA"); T.push("cB")
    op("1"); op("M"); T.pop("cA"); op("-")
    T.push("rowc")
    T.pop("cB")
    A.branch("X", up="HALTBLK", down="PAINTROW", straight="PAINTMAN")

    A.block("PAINTROW")
    tok("r:P"); T.push("w"); tok("s:P")
    K(16); op("b")
    A.jump("PIXHEAD")
    A.endblock()

    A.loop("PIXHEAD", "PIXBODY", "ROWDONE")

    A.block("PIXBODY")
    op("m")
    K(60); op("M")
    T.pop("w"); T.push("w2"); op("}")
    T.push("nb"); K(15); op("M"); T.pop("nb"); op("&")
    tok("s:D")
    K(4); op("M"); T.pop("w2"); op("{")
    T.push("w")
    A.jump("PIXHEAD")
    A.endblock()

    A.block("ROWDONE")
    T.drop("w")
    tok("r:P"); tok("s:P")
    A.jump("PAINTOUT")
    A.endblock()

    A.block("PAINTMAN")
    T.drop("rowc")
    S.get("x"); T.push("xc"); S.put()
    S.get("y"); T.push("yc"); S.put()
    S.home()
    K(16); op("M"); T.pop("yc"); op("*"); op("M")
    T.pop("xc"); op("+")                         # A = 16y + x
    op("M"); op("2"); op("+"); op("N")           # A = -(addr+2)  -> ADDR
    tok("s:D")
    op("9"); tok("s:D")                          # the man pixel
    op("1"); op("N"); tok("s:D")                 # -1 -> SWAP 0
    A.jump("RDK")
    A.endblock()

    # ═══ round loop ══════════════════════════════════════════════════════
    A.block("RDK")
    tok("r:I"); T.push("kv")
    S.get("k"); T.pop("kv"); S.put()
    S.home()
    A.jump("STEPLOOP")
    A.endblock()

    A.block("STEPLOOP")
    S.get("halted"); T.push("h"); S.put()
    S.home()
    T.pop("h")
    A.branch("X", up="HALTBLK", down="FRAME", straight="STEPK")

    A.block("STEPK")
    S.get("k"); T.push("kA"); T.push("kB")
    op("1"); op("M"); T.pop("kA"); op("-")
    S.put()
    S.home()
    T.pop("kB")
    A.branch("X", up="HALTBLK", down="TICK", straight="FRAME")

    # ═══ one LLLM tick ═══════════════════════════════════════════════════
    A.block("TICK")
    S.get("y"); T.push("y1"); T.push("y2"); S.put()
    S.home()
    K(2); op("M"); T.pop("y1"); op("*")          # A = 2y
    op("b")
    A.jump("ROT1")
    A.endblock()

    A.loop("ROT1", "ROT1B", "TICK2")
    A.block("ROT1B")
    op("m"); tok("r:P"); tok("s:P")
    A.jump("ROT1")
    A.endblock()

    A.block("TICK2")
    tok("r:P"); T.push("C"); tok("s:P")
    tok("r:P"); T.push("V"); tok("s:P")
    K(30); T.push("c30")
    K(2); op("M"); T.pop("y2"); op("*"); op("M")
    T.pop("c30"); op("-")                        # A = 30 - 2y
    op("b")
    A.jump("ROT2")
    A.endblock()

    A.loop("ROT2", "ROT2B", "TICK3")
    A.block("ROT2B")
    op("m"); tok("r:P"); tok("s:P")
    A.jump("ROT2")
    A.endblock()

    A.block("TICK3")
    K(60); T.push("c60")
    S.get("x"); T.push("x1"); S.put()
    K(4); op("M"); T.pop("x1"); op("*"); op("M")
    T.pop("c60"); op("-")                        # A = sh = 60 - 4x
    T.push("sA"); T.push("sB")
    T.pop("sA"); op("M"); T.pop("C"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    T.push("cA"); T.push("cB")                   # two copies of the colour
    T.pop("sB"); op("M"); T.pop("V"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    T.push("vv")
    S.get("val"); T.pop("vv"); S.put()
    S.home()
    K(8); op("M"); T.pop("cA"); op("-")          # A = col - 8
    A.branch("X", up="D_LOW", down="D_HIGH", straight="D_DIGIT")

    A.block("D_LOW")
    K(3); op("M"); T.pop("cB"); op("-")          # A = col - 3
    A.branch("X", up="D_SPACE", down="D_WALL", straight="D_ARROW")

    A.block("D_HIGH")
    K(12); op("M"); T.pop("cB"); op("-")         # A = col - 12
    A.branch("X", up="D_PM", down="HALTBLK", straight="D_M")

    A.block("D_SPACE")
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_DIGIT")
    T.drop("cB")
    S.get("val"); T.push("v"); S.put()
    S.get("A_lm"); T.pop("v"); S.put()
    S.home()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_M")
    S.get("A_lm"); T.push("a"); S.put()
    S.get("B_lm"); T.pop("a"); S.put()
    S.home()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_PM")
    S.get("val"); T.push("v"); S.put()
    S.home()
    T.pop("v"); op("M"); op("2"); op("*"); op("M")
    op("1"); op("-")                             # A = 1 - 2*val
    T.push("sg")
    S.get("B_lm"); T.push("b"); S.put()
    T.pop("sg"); op("M"); T.pop("b"); op("*"); op("M")
    S.get("A_lm"); op("+"); S.put()
    S.home()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_ARROW")
    S.get("val"); T.push("vA"); T.push("vB"); S.put()
    S.home()
    K(14); op("M"); T.pop("vA"); op("-")         # A = val - 14
    A.branch("X", up="D_DIR", down="D_XOP", straight="D_HALT")

    A.block("D_DIR")
    S.get("dir"); T.pop("vB"); S.put()
    S.home()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_XOP")
    T.drop("vB")
    S.get("A_lm"); T.push("a1"); T.push("a2"); S.put()
    S.home()
    K(63); op("M"); T.pop("a1"); op("}"); T.push("hi")
    T.pop("a2"); op("N"); T.push("na")
    K(63); op("M"); T.pop("na"); op("}"); T.push("lo")
    T.pop("lo"); op("M"); T.pop("hi"); op("-")   # A = sign(A_lm)
    T.push("sg")
    S.get("dir"); T.push("d0")
    T.pop("sg"); op("M"); T.pop("d0"); op("+")
    T.push("nd"); K(3); op("M"); T.pop("nd"); op("&")
    S.put()
    S.home()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_HALT")
    T.drop("vB")
    S.get("halted"); op("1"); S.put()
    S.home()
    A.jump("STEPLOOP")
    A.endblock()

    A.block("D_WALL")
    S.get("halted"); op("1"); S.put()
    S.home()
    A.jump("STEPLOOP")
    A.endblock()

    A.block("ADVANCE")
    S.get("dir"); T.push("d1"); T.push("d2"); S.put()
    S.home()
    K(4); op("M"); T.pop("d1"); op("*"); T.push("sA")
    K(4); op("M"); T.pop("d2"); op("*"); T.push("sB")
    K(DXT); T.push("tbl")
    T.pop("sA"); op("M"); T.pop("tbl"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    T.push("t"); op("1"); op("M"); T.pop("t"); op("-")
    T.push("dx")
    K(DYT); T.push("tbl")
    T.pop("sB"); op("M"); T.pop("tbl"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    T.push("t"); op("1"); op("M"); T.pop("t"); op("-")
    T.push("dy")
    T.pop("dx"); op("M"); S.get("x"); op("+"); S.put()
    T.pop("dy"); op("M"); S.get("y"); op("+"); S.put()
    S.home()
    A.jump("STEPLOOP")
    A.endblock()

    A.block("HALTBLK")
    op("H")
    A.endblock()

    # ═══ INIT -- emitted LAST so its two long literals sit below every
    #     highway span; only LOADHEAD's column stays reserved here. ════════
    S = Ring(A, "S", LOAD_SLOTS)
    A.S = S
    keep = E.forbidden
    E.forbidden = {A.hw("LOADHEAD")}
    y0 = A.R.take()
    L.put(1, y0, "@")
    E.at(2, y0, "E")
    op("0"); tok("s:S")                          # col
    op("0"); tok("s:S")                          # val
    op("0"); tok("s:S")                          # cw
    op("0"); tok("s:S")                          # vw
    op("0"); tok("s:S")                          # n
    op("0"); tok("s:S")                          # mani
    tok("r:I"); T.push("Wc"); tok("s:S")         # W
    tok("r:I"); T.push("Hc"); tok("s:S")         # H
    K(4)
    for sh in (4, 8, 16, 32):                    # 4 -> 0x4444444444444444
        T.push("v1"); T.push("v2")
        K(sh); op("M")
        T.pop("v1"); op("{"); op("M")
        T.pop("v2"); op("|")
    tok("s:S")                                   # m4
    tok("#%d" % COLW); tok("s:S")
    tok("#%d" % VALW); tok("s:S")
    T.pop("Hc"); op("M"); T.pop("Wc"); op("*")
    op("b")                                      # BP = W*H
    A.jump("LOADHEAD")
    A.endblock()
    E.forbidden = keep

    # ---- checks ---------------------------------------------------------
    A.verify()
    mc.assert_bindings(g, E.ops)
    assert caps["P"] >= 34, "prog ring capacity %d < 34" % caps["P"]
    assert caps["S"] >= len(LOAD_SLOTS) + 2, "state ring capacity %d" % caps["S"]
    assert caps["T"] >= T.peak + 3, "scratch capacity %d < peak %d" % (caps["T"], T.peak)
    used = A.R.y - g["IYLO"]
    assert A.R.y <= g["IYHI"] + 1, "controller overflow: %d rows, has %d" % (
        used, g["IYHI"] - g["IYLO"] + 1)
    p = L.p
    if verbose:
        print("blocks %d  highways used %d/%d  ctrl rows %d  wraps %d"
              % (len(A.blocks), len(A.hw_of), len(forbidden) + len(A.hw_of),
                 used, E.wraps))
        print("ring caps", caps, "scratch peak", T.peak)
    if save_to:
        p.save(save_to)
    return p, A, caps, used


def autobuild(CW=104, CY0=20, save_to=None, verbose=False):
    """Build once to learn the row count, then again with the room trimmed."""
    _, _, _, rows = build(CW=CW, CY0=CY0, CBOT=2000)
    return build(CW=CW, CY0=CY0, CBOT=CY0 + 1 + rows,
                 save_to=save_to, verbose=verbose)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "lane1.man")
    prog, A, caps, rows = autobuild(save_to=out, verbose=True)
    w, h, box = prog.footprint()
    print("saved", out, "footprint", (w, h), "box", box)
