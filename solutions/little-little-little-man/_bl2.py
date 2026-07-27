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
            A frame is 256 DATA + ADDR(man) + DATA 9 + SWAP.  Only the FIRST
            frame paints 256 pixels; later frames send the two changed ones.

THE TWO THINGS THAT SET THE COST, both measured 2026-07-26 and both invisible
from the source:

1. `B SURVIVES A RING ROTATION.`  `r`/`s` clobber A and leave B alone, so a
   two-operand expression over ring slots needs NO scratch:

       K(16); op("M"); S.get("cw"); S.put(); op("*")     # A = 16 * cw

   the rotations inside `get` walk over A only.  Rewriting ATTEST, NONDIG,
   TICK3, MFIN, D_PM, D_XOP and friends this way deleted most of the SCRATCH
   traffic, which was both the tick budget and the row budget: every scratch op
   sits in a DIFFERENT LANE from the state ring, so an S,T,S sequence is a lane
   descent and costs a whole row.  247 -> 216 controller rows, 300k -> 289k
   ticks, and it is why `Scratch` now peaks at 4 instead of 9.

2. `A RING CANNOT ROTATE FASTER THAN ITS RELAY LAP.`  A relay is a six-cell
   cycle (`> R v / ^ s <` -- four of the six cells are forced turns, so six is
   the floor for a directed cycle carrying both an `r` and an `s`), so every
   ring op costs the controller several stalled ticks.  Two thirds of the ticks
   were the controller waiting.  A second relay man is NOT the fix: a room may
   hold only one `@`, and forking one with `Y` deadlocks -- walking into a
   stalled man HALTS BOTH (interp `move_phase`), which a six-cell cycle
   guarantees within a few laps.  The fix that worked was making the rotations
   FEWER (point 1) and putting the PROG-ring rotation loops inline
   (`Asm.tight`, ~10 walked cells per iteration against ~190 for a block loop).
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
STEP_SLOTS = ["halted", "k", "x", "y", "dir", "A_lm", "B_lm", "val",
               "pa", "pc"]     # pa/pc: the pixel the man is standing on


def hw_columns(g, win, nhw, bias, pocket=8):
    """Pick `nhw` HIGHWAY columns out of the interior.

    A highway column is dead to the emitter, so where they go is a real lever:
    put them where the ops are NOT.  `bias` is the fraction of the interior,
    measured from the RIGHT edge, inside which highways are packed -- the right
    margin is the P/D/I lanes, which carry 36 of 1155 pipe ops.

    TWO invariants the allocator must keep, both learned by breaking them:
      * a branch needs TWO ADJACENT free columns, so highways go down in GROUPS
        separated by >= 2 free columns -- never one-on one-off;
      * every lane window must retain a free column, or `_reach` spins forever
        ("lane I unreachable").  The repair pass at the end guarantees it.
    """
    lo, hi = g["IXLO"], g["IXHI"]
    n = hi - lo + 1
    span = min(n, max(int(n * bias), 3 * nhw // 2))
    start = max(lo, hi - span + 1)
    span = hi - start + 1
    k = 1
    while k < 8 and nhw * (2 + k) > span * k:
        k += 1
    ngrp = max(1, (nhw + k - 1) // k)
    pitch = span / float(ngrp)
    cols = set()
    for gi in range(ngrp):
        base = int(start + gi * pitch)
        for j in range(k):
            c = base + j
            if lo < c <= hi and len(cols) < nhw:
                cols.add(c)
    c = hi
    while len(cols) < nhw and c > lo:
        if c not in cols and (c - 1 in cols or c + 1 in cols):
            cols.add(c)
        c -= 1
    # repair 1: every lane window keeps at least three free columns
    for (op, lane), (a, b) in win.items():
        free = [x for x in range(a, b + 1) if x not in cols]
        x = a
        while len(free) < 3 and x <= b:
            if x in cols:
                cols.discard(x)
                free.append(x)
            x += 1
    # repair 2: every lane keeps ONE CONTIGUOUS POCKET wide enough for an inline
    # `tight()` loop.  Without it the P lane -- which lives in the highway-dense
    # right margin -- has no run of free columns at all and the 3-row gadget,
    # which is where the whole STEP tick budget went, cannot be placed.
    for lane in set(k[1] for k in win):
        a1, b1 = win.get(("s", lane), win.get(("r", lane)))
        a2, b2 = win.get(("r", lane), (a1, b1))
        a, b = max(a1, a2), min(b1, b2)
        if b - a + 1 < pocket:
            a, b = min(a1, a2), max(b1, b2)
        start = max(a, min(b - pocket + 1, (a + b - pocket) // 2))
        for x in range(start, min(b, start + pocket - 1) + 1):
            cols.discard(x)
    return sorted(cols)


def build(CW=124, CY0=20, CBOT=900, save_to=None, verbose=False,
          NHW=62, HWBIAS=1.0, SPC=None, TPC=None, PPC=None, LAZY=True,
          POCKET=8, MEN=1, SPAD=6, TPAD=0, PPAD=14):
    g = mc.geometry(CW=CW, CY0=CY0, CBOT=CBOT, SPC=SPC, TPC=TPC, PPC=PPC, MEN=MEN,
                    SPAD=SPAD, TPAD=TPAD, PPAD=PPAD)
    win = mc.lane_windows(g)
    L, caps = mc.build_shell(g)
    hw = hw_columns(g, win, NHW, HWBIAS, POCKET)
    freecols = [c for c in range(g["IXLO"], g["IXHI"] + 1) if c not in hw]
    wrapcols = {freecols[0], freecols[1], freecols[-1], freecols[-2]}
    forbidden = hw + sorted(wrapcols)
    E = mc.Emit(L, g, win, forbidden, wrapcols=wrapcols)
    A = Asm(L, E, g, [c for c in forbidden if c not in wrapcols])
    S = Ring(A, "S", LOAD_SLOTS)
    T = Scratch(A, "T", 9)
    A.S, A.T = S, T
    K, op = A.konst, A.op
    tok = E.tok

    def HOME():
        # With LAZY the ring keeps whatever head the block ends on and jump()
        # aligns it at the join instead; the branch arms then define the state.
        if not LAZY:
            A.S.home()

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
    T.pop("tA"); op("M"); S.get("val"); op("W"); S.put()
    HOME()
    A.jump("ATTEST")
    A.endblock()

    A.block("NONDIG")
    T.drop("tA"); T.drop("tB")
    # B SURVIVES A RING ROTATION, so a two-operand expression over ring slots
    # needs NO scratch at all: set B, then `get`/`put` the other operand -- the
    # rotations in between clobber A only.  That one idiom is what took this
    # block from 26 scratch ops to four.
    K(29); op("M")
    T.pop("cB"); op("*")                         # A = 29c
    op("M"); op("6"); op("W"); op("}")           # A = 29c >> 6
    T.push("h"); K(15); op("M"); T.pop("h"); op("&")     # A = hash slot
    op("M"); op("4"); op("*")                    # A = sh = 4h
    T.push("shB"); op("M")                       # B = sh
    S.get("COLW"); S.put(); op("}")              # A = COLW >> sh
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    op("M"); S.get("col"); op("W"); S.put()      # col := colour nibble
    T.pop("shB"); op("M")
    S.get("VALW"); S.put(); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    op("M"); S.get("val"); op("W"); S.put()
    HOME()
    A.jump("ATTEST")
    A.endblock()

    A.block("ATTEST")
    K(64); op("M")
    T.pop("cC"); op("-")                         # A = z = c - 64
    op("M"); op("N"); op("|")                    # A = (-z) | z
    T.push("z"); K(63); op("M"); T.pop("z"); op("}")
    op("M"); op("1"); op("+")                    # A = 1 + (-1|0)  -> 1 iff '@'
    T.push("is")
    K(16); op("M"); S.get("cw"); S.put(); op("*")     # A = 16*cw
    op("M"); S.get("col"); S.put(); op("+")           # A = 16cw + col
    op("M"); S.get("cw"); op("W"); S.put()
    K(16); op("M"); S.get("vw"); S.put(); op("*")
    op("M"); S.get("val"); S.put(); op("+")
    op("M"); S.get("vw"); op("W"); S.put()
    S.get("n"); op("M"); op("1"); op("+"); S.put()    # n := n+1, A = n+1, B = n
    T.pop("is"); op("*")                              # A = is * n
    op("M"); S.get("mani"); op("+"); S.put()
    S.get("n"); S.put(); op("M")                      # B = n+1
    S.get("W"); S.put(); op("W"); op("%")             # A = (n+1) % W
    op("M"); HOME(); op("W")
    A.branch("X", up="HALTBLK", down="LOADHEAD", straight="ROWEND")

    A.block("ROWEND")
    S.get("W"); S.put(); op("M"); op("4"); op("*"); op("N")
    T.push("nw"); K(64); op("M"); T.pop("nw"); op("+")   # A = 64 - 4W
    T.push("shB"); op("M")
    S.get("cw"); op("{"); tok("s:P"); op("0"); S.put()
    T.pop("shB"); op("M")
    S.get("vw"); op("{"); tok("s:P"); op("0"); S.put()  # noqa
    HOME()
    A.jump("LOADHEAD")
    A.endblock()

    # ═══ PAD the plane to 16 rows ════════════════════════════════════════
    A.block("PADSET")
    S.get("H"); S.put(); op("N")
    T.push("nh"); K(16); op("M"); T.pop("nh"); op("+")   # A = 16 - H
    op("b")
    HOME()
    A.tight(["0", "s:P", "s:P"])
    A.jump("FIXSET")
    A.endblock()

    # ═══ WALL PASS: recolour the room's horizontal walls ═════════════════
    A.block("FIXSET")
    K(16); op("b")
    HOME()
    A.jump("FIXHEAD")
    A.endblock()

    A.loop("FIXHEAD", "FIXBODY", "STEPSET")

    A.block("FIXBODY")
    op("m")
    tok("r:P")                                   # A = C[row]
    T.push("C1"); T.push("C2"); T.push("C3")
    op("1"); op("M"); T.pop("C1"); op("}")       # A = C>>1
    T.push("s")
    S.get("m4"); S.put(); T.push("m4c"); HOME()
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
    S.get("mani"); S.put(); T.push("mani");
    S.get("W"); S.put(); T.push("Wc");
    HOME()
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
    op("0"); tok("s:S")                          # pa
    op("0"); tok("s:S")                          # pc
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
    A.jump("MANDRAW")
    A.endblock()

    # ═══ DELTA frame: erase the old man pixel, then redraw ═══════════════
    # Only TWO pixels ever change between consecutive frames, so a frame is
    # five sends instead of 258.  This is the whole tick budget: the full
    # repaint runs exactly once, for the very first frame.
    A.block("DELTA")
    S.get("pa"); S.put(); op("M"); op("2"); op("+"); op("N"); tok("s:D")
    S.get("pc"); S.put(); op("M"); HOME(); op("W"); tok("s:D")
    A.jump("MANDRAW")
    A.endblock()

    # ═══ MANDRAW: (re)read the colour under the man, draw him, commit ════
    A.block("MANDRAW")
    K(2); op("M"); S.get("y"); S.put(); op("*"); op("b")
    A.tight(["r:P", "s:P"])
    tok("r:P"); T.push("C"); tok("s:P")
    K(2); op("M"); S.get("y"); S.put(); op("*"); op("N")
    T.push("n2"); K(31); op("M"); T.pop("n2"); op("+")   # A = 31 - 2y
    op("b")
    A.tight(["r:P", "s:P"])
    HOME()
    A.jump("MFIN")
    A.endblock()

    A.block("MFIN")
    K(4); op("M"); S.get("x"); S.put(); op("*"); op("N")
    T.push("n4"); K(60); op("M"); T.pop("n4"); op("+")   # A = sh = 60 - 4x
    op("M"); T.pop("C"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    op("M"); S.get("pc"); op("W"); S.put()       # pc := colour under the man
    K(16); op("M"); S.get("y"); S.put(); op("*")
    op("M"); S.get("x"); S.put(); op("+")        # A = 16y + x
    op("M"); S.get("pa"); op("W"); S.put()       # pa := addr, A = addr
    op("M"); HOME(); op("W")
    op("M"); op("2"); op("+"); op("N"); tok("s:D")
    op("9"); tok("s:D")
    op("1"); op("N"); tok("s:D")                 # -1 -> SWAP 1 (preserve)
    A.jump("RDK")
    A.endblock()

    # ═══ round loop ══════════════════════════════════════════════════════
    A.block("RDK")
    tok("r:I"); op("M"); S.get("k"); op("W"); S.put()
    HOME()
    A.jump("STEPLOOP")
    A.endblock()

    A.block("STEPLOOP")
    S.get("halted"); S.put(); op("M"); HOME(); op("W")
    A.branch("X", up="HALTBLK", down="DELTA", straight="STEPK")

    A.block("STEPK")
    S.get("k"); op("M"); op("1"); op("-"); op("N"); S.put()   # k := k-1
    op("M"); HOME(); op("W")
    op("M"); op("1"); op("+")                    # A = the OLD k
    A.branch("X", up="HALTBLK", down="TICK", straight="DELTA")

    # ═══ one LLLM tick ═══════════════════════════════════════════════════
    A.block("TICK")
    K(2); op("M"); S.get("y"); S.put(); op("*")  # A = 2y
    op("b")
    A.tight(["r:P", "s:P"])
    tok("r:P"); T.push("C"); tok("s:P")
    tok("r:P"); T.push("V"); tok("s:P")
    K(2); op("M"); S.get("y"); S.put(); op("*"); op("N")
    T.push("n2"); K(30); op("M"); T.pop("n2"); op("+")   # A = 30 - 2y
    op("b")
    A.tight(["r:P", "s:P"])
    HOME()
    A.jump("TICK3")
    A.endblock()

    A.block("TICK3")
    K(4); op("M"); S.get("x"); S.put(); op("*"); op("N")
    T.push("n4"); K(60); op("M"); T.pop("n4"); op("+")   # A = sh = 60 - 4x
    T.push("sB"); op("M")
    T.pop("C"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    T.push("cA"); T.push("cB")                   # two copies of the colour
    T.pop("sB"); op("M"); T.pop("V"); op("}")
    T.push("t"); K(15); op("M"); T.pop("t"); op("&")
    op("M"); S.get("val"); op("W"); S.put()
    HOME()
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
    S.get("val"); S.put(); op("M"); S.get("A_lm"); op("W"); S.put()
    HOME()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_M")
    S.get("A_lm"); S.put(); op("M"); S.get("B_lm"); op("W"); S.put()
    HOME()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_PM")
    S.get("val"); S.put(); T.push("v");
    HOME()
    T.pop("v"); op("M"); op("2"); op("*"); op("M")
    op("1"); op("-")                             # A = 1 - 2*val
    T.push("sg")
    S.get("B_lm"); S.put(); T.push("b");
    T.pop("sg"); op("M"); T.pop("b"); op("*"); op("M")
    S.get("A_lm"); op("+"); S.put()
    HOME()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_ARROW")
    S.get("val"); S.put(); T.push("vA"); T.push("vB");
    HOME()
    K(14); op("M"); T.pop("vA"); op("-")         # A = val - 14
    A.branch("X", up="D_DIR", down="D_XOP", straight="D_HALT")

    A.block("D_DIR")
    S.get("dir"); T.pop("vB"); S.put()
    HOME()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_XOP")
    T.drop("vB")
    S.get("A_lm"); S.put(); T.push("a1"); T.push("a2");
    HOME()
    K(63); op("M"); T.pop("a1"); op("}"); T.push("hi")
    T.pop("a2"); op("N"); T.push("na")
    K(63); op("M"); T.pop("na"); op("}"); T.push("lo")
    T.pop("lo"); op("M"); T.pop("hi"); op("-")   # A = sign(A_lm)
    T.push("sg")
    S.get("dir"); T.push("d0")
    T.pop("sg"); op("M"); T.pop("d0"); op("+")
    T.push("nd"); K(3); op("M"); T.pop("nd"); op("&")
    S.put()
    HOME()
    A.jump("ADVANCE")
    A.endblock()

    A.block("D_HALT")
    T.drop("vB")
    S.get("halted"); op("1"); S.put()
    HOME()
    A.jump("STEPLOOP")
    A.endblock()

    A.block("D_WALL")
    S.get("halted"); op("1"); S.put()
    HOME()
    A.jump("STEPLOOP")
    A.endblock()

    A.block("ADVANCE")
    S.get("dir"); S.put(); T.push("d1"); T.push("d2");
    HOME()
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
    HOME()
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
    mx = min(c for c in freecols if c + 1 in freecols)
    L.put(mx, y0, "@")
    E.at(mx + 1, y0, "E")
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


def autobuild(CW=124, CY0=20, save_to=None, verbose=False, **kw):
    """Build once to learn the row count, then again with the room trimmed."""
    _, _, _, rows = build(CW=CW, CY0=CY0, CBOT=2000, **kw)
    return build(CW=CW, CY0=CY0, CBOT=CY0 + 1 + rows,
                 save_to=save_to, verbose=verbose, **kw)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "lane1.man")
    prog, A, caps, rows = autobuild(save_to=out, verbose=True)
    w, h, box = prog.footprint()
    print("saved", out, "footprint", (w, h), "box", box)
