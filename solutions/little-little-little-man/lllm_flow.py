#!/usr/bin/env python3
"""The LLLM interpreter, expressed as a machine-independent op/CFG program.

Separating SEMANTICS (this file, simulated in Python by lllm_sim.py) from
GEOMETRY (build_lllm.py) is the only way this is debuggable: a wrong answer is
found in milliseconds against lllm_model.py instead of by bisecting a 200k-cell
grid on the Rust interpreter.

MACHINE MODEL
  registers  A, B, BP        -- the controller man's own, signed 64-bit wrapping
  holders    named 1-word swap cells, one tiny room each.  The holder man loops
             `s` then `r`, so the controller MUST access one as `hr` ... `hw`
             (read-then-write) and may never issue two `hr` on the same holder
             without an `hw` in between.  `hr` clobbers A; every update is
             therefore written as a read-modify-write.
  ring       a 32-slot FIFO (CTRL -> pipe -> relay -> pipe -> CTRL) holding the
             packed program: slot 2y = OP row word y, slot 2y+1 = VAL row word y.
             `rr` pops the head, `rs` pushes the tail; PH tracks the phase.
  input      `in`  -> A
  display    `da` ADDR, `dd` DATA, `ds` SWAP

CONTROL FLOW
  ('br', L)    emits  b d  -- if A > 0 jump to L, else fall through (A, B kept)
  ('brbp', L)  emits  d    -- if BP > 0 jump to L  (BP used as a loop counter)
  ('go', L)    unconditional
Everything is built from those, so every taken branch leaves the code row
heading SOUTH and every fall-through continues along the row -- which is what
makes the 2-rows-per-block layout in build_lllm.py possible.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lllm_tables import (C, CLASS_COLOUR, CHAR_CLASS, COLOUR_WORD, pack_table)

# --------------------------------------------------------------------------
# the perfect hash that classifies every non-digit LLLM character
#   h(c) = ((c * HASH_MUL) >> HASH_SHIFT) % HASH_MOD      (injective, verified)
# --------------------------------------------------------------------------
HASH_MUL = 55
HASH_SHIFT = 4
HASH_MOD = 15

NONDIGIT_CHARS = [ch for ch in CHAR_CLASS if not ch.isdigit()]


def _hash(c):
    return ((c * HASH_MUL) >> HASH_SHIFT) % HASH_MOD


def build_class_word():
    """Pack {hash(ch): class(ch)} for every non-digit character into one i64."""
    slots = {}
    for ch in NONDIGIT_CHARS:
        h = _hash(ord(ch))
        assert h not in slots, ("hash collision", ch, h)
        slots[h] = CHAR_CLASS[ch]
    return pack_table(slots)


CLASS_WORD = build_class_word()

DIGIT_LO = ord("0")
DIGIT_SPAN = 9
AT_CHAR = ord("@")

NIB = 4                 # bits per packed cell
ROW_W = 16              # cells per packed row word
SH_TOP = NIB * (ROW_W - 1)      # shift of cell x=0
ADDR_MOD = 16           # ADDR = 16*y + x
RING_SLOTS = 2 * ROW_W
DISPLAY_CELLS = 256
SWAP_KEEP = 1

# Setup-phase scalars are ALIASED onto step-phase scalars that are still dead
# when setup runs (every step scalar below is first written in RENDER_DONE,
# which happens after the last use of its setup alias).  Each alias removed is
# one whole holder room and 5 columns of controller width, and the width is
# what the man walks.  lllm_sim.py re-checks the read/write pairing after the
# rename, so a bad alias shows up as a Python failure, not a silent one.
ALIAS = {
    "TMPC": "AL", "TMPV": "BL", "CHR": "KK", "CX": "PA",
    "CY": "PCOL", "SHPAD": "HD",
}
# WW and HHT deliberately keep their own rooms: the frame-0 raster loops over
# the W x H region, so they are still live long after RETM/CD come alive.

HOLDERS = [
    "CD", "SH", "OPR", "VLR", "AD", "HD", "AL", "BL", "KK", "PH",
    "PA", "PCOL", "RETM", "ADS", "X0", "Y0", "X1", "Y1", "WW", "HHT",
]


class Flow(object):
    """Ordered basic blocks of tokens."""

    def __init__(self):
        self.blocks = {}
        self.order = []
        self.cur = None

    def at(self, label):
        assert label not in self.blocks, label
        self.cur = []
        self.blocks[label] = self.cur
        self.order.append(label)
        return self

    def e(self, *tokens):
        self.cur.extend(tokens)
        return self

    # ---- primitive tokens -------------------------------------------------
    def lit(self, n):
        assert n >= 0
        return self.e(str(n) if n < 10 else ("lit", n))

    def hr(self, h):
        return self.e(("hr", ALIAS.get(h, h)))

    def hw(self, h):
        return self.e(("hw", ALIAS.get(h, h)))

    def get(self, h):
        """A := holder h, holder unchanged (read + write straight back)."""
        h = ALIAS.get(h, h)
        return self.e(("hr", h), ("hw", h))

    def br(self, label):
        return self.e(("br", label))

    def brbp(self, label):
        return self.e(("brbp", label))

    def go(self, label):
        return self.e(("go", label))

    # ---- small arithmetic macros -----------------------------------------
    def sub_const(self, n):
        """A := A - n."""
        self.e("M")
        self.lit(n)
        return self.e("W", "-")

    def const_sub(self, n):
        """A := n - A."""
        self.e("M")
        self.lit(n)
        return self.e("-")

    def add_const(self, n):
        """A := A + n."""
        self.e("M")
        self.lit(n)
        return self.e("+")

    def mul_const(self, n):
        self.e("M")
        self.lit(n)
        return self.e("*")

    def mod_const(self, n):
        self.e("M")
        self.lit(n)
        return self.e("W", "%")

    def shr_const(self, n):
        self.e("M")
        self.lit(n)
        return self.e("W", "}")

    def shl_const(self, n):
        self.e("M")
        self.lit(n)
        return self.e("W", "{")

    def br_ne0(self, label):
        """Jump to `label` unless A == 0.  Falls through with A == 0."""
        self.br(label)
        self.e("N")
        return self.br(label)

    def set_const(self, holder, n):
        self.hr(holder)
        self.lit(n)
        return self.hw(holder)

    def copy_holder(self, dst, src):
        self.hr(dst)
        self.get(src)
        return self.hw(dst)

    def nib_extract(self):
        """A := (A >> B_shift) & 15 -- expects A=word and the shift already in B."""
        self.e("}")
        return self.mod_const(ROW_W)


# Debugging aid: {block_label: [holder, ...]} emits those holders through an
# ordinary output room at the top of that block.  build_lllm.py wires the room
# only when this is non-empty, so a shipping build is unaffected.
DEBUG_EMIT = {}


def build_flow():
    f = Flow()
    real_at = f.at

    def at(label):
        real_at(label)
        for h in DEBUG_EMIT.get(label, ()):
            f.get(h)
            f.e(("ot",))
        return f

    f.at = at

    # ==================================================================
    # BOOT: W, H, derived constants
    # ==================================================================
    f.at("BOOT")
    f.hr("WW").e(("in",)).hw("WW")
    f.hr("HHT").e(("in",)).hw("HHT")
    f.hr("SHPAD")
    f.get("WW")
    f.const_sub(ROW_W)               # A = 16 - W
    f.mul_const(NIB)                 # A = 4*(16-W)
    f.hw("SHPAD")
    f.hr("X0").lit(1).e("N").hw("X0")        # X0 = -1  (no '+' seen yet)
    f.go("CELL_LOOP")

    # ==================================================================
    # PASS 1 -- read W*H characters, classify, Horner-pack into row words
    # ==================================================================
    f.at("CELL_LOOP")
    f.hr("TMPC").hr("TMPV").hr("CHR")
    f.e(("in",))
    f.hw("CHR")                       # A = c
    f.sub_const(DIGIT_LO)             # A = c - 48
    f.e("N").br("NONDIGIT")           # c < 48
    f.e("N")
    f.sub_const(DIGIT_SPAN).br("NONDIGIT")   # c > 57
    # --- digit: A = c-57, so value = A + 9
    f.add_const(DIGIT_SPAN)
    f.hw("TMPV")
    f.lit(C["DIGIT"]).hw("TMPC")
    f.go("CELL_CODED")

    f.at("NONDIGIT")
    f.lit(0).hw("TMPV")
    f.get("CHR")
    f.mul_const(HASH_MUL)
    f.shr_const(HASH_SHIFT)
    f.mod_const(HASH_MOD)
    f.mul_const(NIB)
    f.e("M")
    f.lit(CLASS_WORD)
    f.nib_extract()
    f.hw("TMPC")
    f.go("CELL_CODED")

    # --- '@' records the start address ---------------------------------
    f.at("CELL_CODED")
    f.get("CHR")
    f.sub_const(AT_CHAR)
    f.br_ne0("NOT_AT")
    f.hr("ADS")
    f.get("CY").mul_const(ADDR_MOD).e("M")
    f.get("CX").e("+")
    f.hw("ADS")
    f.go("NOT_AT")

    # --- '+' drives the room-rectangle finder --------------------------
    f.at("NOT_AT")
    f.get("TMPC")
    f.sub_const(C["ADD"])
    f.br_ne0("NOT_PLUS")
    f.get("X0").e("N").br("FIRST_PLUS")       # X0 < 0 -> first '+'
    f.go("LATER_PLUS")

    f.at("FIRST_PLUS")
    f.copy_holder("X0", "CX")
    f.copy_holder("Y0", "CY")
    f.copy_holder("X1", "CX")
    f.copy_holder("Y1", "CY")
    f.go("NOT_PLUS")

    f.at("LATER_PLUS")
    f.get("CY").e("M").get("Y0").e("-")       # A = y0 - cy
    f.br_ne0("PLUS_CHK_X")
    f.copy_holder("X1", "CX")
    f.go("PLUS_CHK_X")

    f.at("PLUS_CHK_X")
    f.get("CX").e("M").get("X0").e("-")       # A = x0 - cx
    f.br_ne0("NOT_PLUS")
    f.copy_holder("Y1", "CY")
    f.go("NOT_PLUS")

    # --- Horner accumulate into the row words --------------------------
    f.at("NOT_PLUS")
    f.hr("OPR")
    f.shl_const(NIB).e("M")
    f.get("TMPC").e("+")
    f.hw("OPR")
    f.hr("VLR")
    f.shl_const(NIB).e("M")
    f.get("TMPV").e("+")
    f.hw("VLR")
    # cx += 1 ; row finished?
    f.hr("CX").add_const(1).hw("CX")
    f.e("M")
    f.get("WW").e("-")                        # A = W - (cx+1)
    f.br("CELL_LOOP")
    f.go("ROW_END")

    f.at("ROW_END")
    f.set_const("CX", 0)
    f.hr("OPR").e("M").get("SHPAD").e("W", "{").e(("rs",))
    f.lit(0).hw("OPR")
    f.hr("VLR").e("M").get("SHPAD").e("W", "{").e(("rs",))
    f.lit(0).hw("VLR")
    f.hr("CY").add_const(1).hw("CY")
    f.e("M")
    f.get("HHT").e("-")                       # A = H - (cy+1)
    f.br("CELL_LOOP")
    f.go("PAD_ROWS")

    # --- pad rows H..15 with zero words --------------------------------
    f.at("PAD_ROWS")
    f.get("CY").const_sub(ROW_W).e("b")       # BP = 16 - H
    f.go("PAD_LOOP")

    f.at("PAD_LOOP")
    f.brbp("PAD_BODY")
    f.go("ROOM_CHECK")

    f.at("PAD_BODY")
    f.lit(0).e(("rs",))
    f.lit(0).e(("rs",))
    f.e("m")
    f.go("PAD_LOOP")

    # ==================================================================
    # room rectangle sanity -- fall back to the whole-grid perimeter
    # ==================================================================
    f.at("ROOM_CHECK")
    f.get("X0").e("N").br("FALLBACK")         # never saw a '+'
    f.get("X1").e("M").get("X0").e("-")
    f.br_ne0("ROOM_CHECK2")
    f.go("FALLBACK")

    f.at("ROOM_CHECK2")
    f.get("Y1").e("M").get("Y0").e("-")
    f.br_ne0("RENDER_INIT")
    f.go("FALLBACK")

    f.at("FALLBACK")
    f.set_const("X0", 0)
    f.set_const("Y0", 0)
    f.hr("X1").get("WW").sub_const(1).hw("X1")
    f.hr("Y1").get("HHT").sub_const(1).hw("Y1")
    f.go("RENDER_INIT")

    # ==================================================================
    # frame 0 raster: 256 pixels straight down the display in reading order
    # ==================================================================
    f.at("RENDER_INIT")
    f.set_const("RETM", 1)
    f.set_const("AD", 0)
    f.go("R_LOOP")

    f.at("R_LOOP")
    f.hr("SH")
    f.get("AD").mod_const(ADDR_MOD)           # A = x
    f.mul_const(NIB).e("M")
    f.lit(SH_TOP).e("-")                      # A = 60 - 4x
    f.hw("SH")
    f.get("AD").mod_const(ADDR_MOD)
    f.br("FETCH_SAME")                        # x > 0 -> row already cached
    f.get("AD").e(("da",))                    # x == 0: park the cursor on row y
    f.go("FETCH_ROW")

    f.at("R_EMIT")
    f.get("CD").mul_const(NIB).e("M")
    f.lit(COLOUR_WORD)
    f.nib_extract()
    f.e(("dd",))
    f.hr("AD").add_const(1).hw("AD")
    f.mod_const(ADDR_MOD).e("M")
    f.get("WW").e("-")                        # A = W - x
    f.br("R_CHK")                             # still inside the row
    f.get("WW").const_sub(ROW_W).e("M")       # W < 16: skip the row's tail
    f.hr("AD").e("+").hw("AD")                # AD = 16*(y+1)
    f.go("R_CHK")

    f.at("R_CHK")
    f.get("AD").shr_const(NIB).e("M")
    f.get("HHT").e("-")                       # A = H - y
    f.br("R_LOOP")
    f.go("RENDER_DONE")

    f.at("RENDER_DONE")
    f.set_const("RETM", 0)
    f.copy_holder("AD", "ADS")
    f.copy_holder("PA", "ADS")
    f.set_const("PCOL", 0)
    f.set_const("HD", 1)
    f.set_const("AL", 0)
    f.set_const("BL", 0)
    f.set_const("KK", 0)
    f.hr("SH")
    f.get("AD").mod_const(ADDR_MOD)
    f.mul_const(NIB).e("M")
    f.lit(SH_TOP).e("-")
    f.hw("SH")
    f.go("FETCH_ROW")

    # ==================================================================
    # shared cell fetch: FETCH_ROW -> FETCH_SAME -> WALLCHK -> dispatch
    # ==================================================================
    f.at("FETCH_ROW")
    f.get("AD").shr_const(NIB)                # A = y
    f.mul_const(2).e("M")                     # B = 2y
    f.get("PH").e("W", "-")                   # A = 2y - PH
    f.mod_const(RING_SLOTS)
    f.e("b")
    f.go("ROT_LOOP")

    f.at("ROT_LOOP")
    f.brbp("ROT_BODY")
    f.go("RING_READ")

    f.at("ROT_BODY")
    f.e(("rr",), ("rs",), "m")
    f.go("ROT_LOOP")

    f.at("RING_READ")
    f.hr("OPR").e(("rr",)).hw("OPR").e(("rs",))
    f.hr("VLR").e(("rr",)).hw("VLR").e(("rs",))
    f.hr("PH")
    f.get("AD").shr_const(NIB)
    f.mul_const(2).add_const(2)
    f.mod_const(RING_SLOTS)
    f.hw("PH")
    f.go("FETCH_SAME")

    f.at("FETCH_SAME")
    f.hr("CD")
    f.get("OPR").e("M")
    f.get("SH").e("W")
    f.nib_extract()
    f.hw("CD")
    f.go("WALLCHK")

    # --- is the cell at AD on the room rectangle? ----------------------
    f.at("WALLCHK")
    f.get("AD").mod_const(ADDR_MOD).e("M")    # B = x
    f.get("X0").e("-")                        # A = x0 - x
    f.br("WALL_NO")                           # x < x0
    f.get("AD").mod_const(ADDR_MOD).e("M")
    f.get("X1").e("-").e("N")                 # A = x - x1
    f.br("WALL_NO")                           # x > x1
    f.go("WALLCHK_Y")

    f.at("WALLCHK_Y")
    f.get("AD").shr_const(NIB).e("M")         # B = y
    f.get("Y0").e("-")
    f.br("WALL_NO")                           # y < y0
    f.get("AD").shr_const(NIB).e("M")
    f.get("Y1").e("-").e("N")
    f.br("WALL_NO")                           # y > y1
    f.go("WALLCHK_EDGE")

    f.at("WALLCHK_EDGE")
    f.get("AD").mod_const(ADDR_MOD).e("M")
    f.get("X0").e("-")
    f.br_ne0("WALL_E2")
    f.go("WALL_YES")

    f.at("WALL_E2")
    f.get("AD").mod_const(ADDR_MOD).e("M")
    f.get("X1").e("-")
    f.br_ne0("WALL_E3")
    f.go("WALL_YES")

    f.at("WALL_E3")
    f.get("AD").shr_const(NIB).e("M")
    f.get("Y0").e("-")
    f.br_ne0("WALL_E4")
    f.go("WALL_YES")

    f.at("WALL_E4")
    f.get("AD").shr_const(NIB).e("M")
    f.get("Y1").e("-")
    f.br_ne0("WALL_NO")
    f.go("WALL_YES")

    f.at("WALL_YES")
    f.set_const("CD", C["WALL"])
    f.go("WALL_NO")

    f.at("WALL_NO")
    f.get("RETM")
    f.br("R_EMIT")
    f.go("STEP_TAIL")

    f.at("STEP_TAIL")
    f.get("CD").sub_const(C["WALL"])
    f.br_ne0("STEP")
    f.set_const("CD", C["DEAD"])
    f.go("STEP")

    # ==================================================================
    # round / step loop
    # ==================================================================
    f.at("NEXT_ROUND")
    f.hr("KK").e(("in",)).hw("KK")
    f.go("STEP")

    f.at("STEP")
    f.get("CD").sub_const(C["DEAD"])
    f.br_ne0("STEP_ALIVE")
    f.go("ROUND_END")

    f.at("STEP_ALIVE")
    f.get("KK")
    f.br("DOTICK")
    f.go("ROUND_END")

    f.at("DOTICK")
    f.hr("KK").sub_const(1).hw("KK")
    f.get("CD").e("M")                        # B = CD for the whole dispatch
    f.lit(5).e("-").br("D_LOW")
    f.lit(8).e("-").br("D_MID")
    f.lit(9).e("-").br("OP_X")
    f.lit(10).e("-").br("OP_H")
    f.go("OP_DIGIT")

    f.at("D_LOW")
    f.lit(1).e("-").br("ADVANCE")             # CD == 0, nop
    f.lit(3).e("-").br("D_LOW2")
    f.lit(4).e("-").br("OP_S")
    f.go("OP_W")

    f.at("D_LOW2")
    f.lit(2).e("-").br("OP_N")
    f.go("OP_E")

    f.at("D_MID")
    f.lit(6).e("-").br("OP_M")
    f.lit(7).e("-").br("OP_ADD")
    f.go("OP_SUB")

    f.at("OP_N")
    f.set_const("HD", 0)
    f.go("ADVANCE")

    f.at("OP_E")
    f.set_const("HD", 1)
    f.go("ADVANCE")

    f.at("OP_S")
    f.set_const("HD", 2)
    f.go("ADVANCE")

    f.at("OP_W")
    f.set_const("HD", 3)
    f.go("ADVANCE")

    f.at("OP_M")
    f.copy_holder("BL", "AL")
    f.go("ADVANCE")

    f.at("OP_ADD")
    f.get("BL").e("M")                         # B = BL
    f.hr("AL").e("+").hw("AL")                 # AL = AL + BL
    f.go("ADVANCE")

    f.at("OP_SUB")
    f.get("BL").e("M")
    f.hr("AL").e("-").hw("AL")                 # AL = AL - BL
    f.go("ADVANCE")

    f.at("OP_X")
    f.get("AL")
    f.br("X_CW")
    f.e("N").br("X_CCW")
    f.go("ADVANCE")

    f.at("X_CW")
    f.hr("HD").add_const(1).mod_const(4).hw("HD")
    f.go("ADVANCE")

    f.at("X_CCW")
    f.hr("HD").sub_const(1).mod_const(4).hw("HD")
    f.go("ADVANCE")

    f.at("OP_H")
    f.set_const("CD", C["DEAD"])
    f.go("STEP")

    f.at("OP_DIGIT")
    f.hr("AL")
    f.get("VLR").e("M")
    f.get("SH").e("W")
    f.nib_extract()
    f.hw("AL")
    f.go("ADVANCE")

    # ==================================================================
    # advance the man one cell
    # ==================================================================
    f.at("ADVANCE")
    f.get("HD").e("M")
    f.lit(1).e("-").br("ADV_N")
    f.lit(2).e("-").br("ADV_E")
    f.lit(3).e("-").br("ADV_S")
    f.go("ADV_W")

    f.at("ADV_E")
    f.hr("AD").add_const(1).hw("AD")
    f.hr("SH").sub_const(NIB).hw("SH")
    f.go("FETCH_SAME")

    f.at("ADV_W")
    f.hr("AD").sub_const(1).hw("AD")
    f.hr("SH").add_const(NIB).hw("SH")
    f.go("FETCH_SAME")

    f.at("ADV_N")
    f.hr("AD").sub_const(ADDR_MOD).hw("AD")
    f.go("FETCH_ROW")

    f.at("ADV_S")
    f.hr("AD").add_const(ADDR_MOD).hw("AD")
    f.go("FETCH_ROW")

    # ==================================================================
    # end of a round: delta frame, then wait for the next k
    # ==================================================================
    f.at("ROUND_END")
    f.get("PA").e(("da",))
    f.get("PCOL").e(("dd",))
    f.get("AD").e(("da",))
    f.lit(9).e(("dd",))
    f.lit(SWAP_KEEP).e(("ds",))
    f.copy_holder("PA", "AD")
    f.hr("PCOL")
    f.get("CD").mul_const(NIB).e("M")
    f.lit(COLOUR_WORD)
    f.nib_extract()
    f.hw("PCOL")
    f.go("NEXT_ROUND")

    return f


if __name__ == "__main__":
    fl = build_flow()
    print("blocks:", len(fl.blocks))
    print("tokens:", sum(len(v) for v in fl.blocks.values()))
    print("CLASS_WORD:", CLASS_WORD, "COLOUR_WORD:", COLOUR_WORD)
