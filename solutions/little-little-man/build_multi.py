#!/usr/bin/env python3
"""LLM interpreter slice: up to three independent rooms, without target pipes.

This variant extends subset-room.man with synchronous multi-man scheduling and
arbitrary room placement.  It deliberately remains a separate candidate while
pipe topology/state is still absent.
"""
import os

import build_subset as subset


HERE = os.path.dirname(__file__)

# Ten phase-aliased globals occupy the cheap single-digit RAM addresses.
W = LEFT = RA = 0
HH = RIGHT = RB = 1
IX = POS = 2
IY = DIR = 3
NMAN = 4
MID = 5
TMP = HALT = 6
STAGE = CHR = CH = 7
DEAD = TOP = 8
K = BOTTOM = 9

CELL0 = 32
STATE0 = 10
MAX_MEN = 3
STATE_STRIDE = 8
S_POS, S_DIR, S_A, S_B, S_HALT = range(5)
RAM_N = 288


class Flow(subset.Flow):
    """Flow macros with safe access to synthesized and dynamic RAM addresses."""

    def loadv(self):
        """A := RAM[A]."""
        return self.e("M").const(0).e("sc", "W", "sc", "rr")

    def storev(self):
        """RAM[B] := A."""
        # Scratch FIFO holds [address, payload].
        return (
            self.e("W", "sp", "W", "sp")
            .const(1).e("sc", "rp", "sc", "rp", "sc")
        )

    def state_addr(self, field):
        return (
            self.load(MID).e("M")
            .const(3).e("W", "{", "sp")
            .const(STATE0 + field).e("M", "rp", "+")
        )

    def state_load(self, field):
        return self.state_addr(field).loadv()

    def state_store(self, field):
        return self.store(STAGE).state_addr(field).e("M").load(STAGE).storev()

    def cell_addr(self, index_addr):
        return (
            self.load(index_addr).e("sp")
            .const(CELL0).e("M", "rp", "+")
        )

    def cell_load(self, index_addr):
        return self.cell_addr(index_addr).loadv()

    def cell_store(self, index_addr):
        return self.store(STAGE).cell_addr(index_addr).e("M").load(STAGE).storev()

    def raw(self, index_addr=None):
        if index_addr is not None:
            self.cell_load(index_addr)
        return self.e(*(["M", "2", "W", "/"] * 4))

    def index(self, x_addr, y_addr, dst=TMP):
        # A = 16*y+x.
        return (
            self.load(y_addr).e("M")
            .const(4).e("W", "{", "M")
            .load(x_addr).e("+").store(dst)
        )


def emit_color_dispatch(f):
    """Dispatch CH to the static interior-cell color in A."""
    mapping = {
        72: 3, 118: 3, 94: 3, 62: 3, 60: 3, 88: 3,
        77: 12, 43: 10, 45: 10, 115: 13, 114: 13,
    }
    f.subc(CH, 48).br("COLOR_DIG_HI", "COLOR_DIGIT", "COLOR_MAP_0")
    f.at("COLOR_DIG_HI").subc(CH, 57).br(
        "COLOR_MAP_0", "COLOR_DIGIT", "COLOR_DIGIT"
    )
    items = list(mapping.items())
    for index, (ascii_value, color) in enumerate(items):
        label = f"COLOR_MAP_{index}"
        if label not in f.blocks:
            f.at(label)
        next_label = (
            f"COLOR_MAP_{index + 1}" if index + 1 < len(items) else "COLOR_ZERO"
        )
        f.subc(CH, ascii_value).br(next_label, f"COLOR_C{color}", next_label)
    f.at("COLOR_WALL").const(4).go("COLOR_WRITE")
    f.at("COLOR_DIGIT").const(8).go("COLOR_WRITE")
    f.at("COLOR_ZERO").const(0).go("COLOR_WRITE")
    for color in sorted(set(mapping.values())):
        f.at(f"COLOR_C{color}").const(color).go("COLOR_WRITE")


def build_flow():
    f = Flow()
    f.at("START").inp().store(W).inp().store(HH)
    for addr in (IX, IY, NMAN, MID, DEAD, K):
        f.const(0).store(addr)
    for man in range(MAX_MEN):
        f.const(man).store(MID)
        f.const(1).e("N").state_store(S_POS)
        f.const(1).state_store(S_HALT)
    f.const(0).store(MID)
    f.go("READ_TEST")

    # Read source into fixed-stride 16x16 storage.
    f.at("READ_TEST").bin("-", IY, HH).br("AFTER_READ", "AFTER_READ", "READ_ROW")
    f.at("READ_ROW").bin("-", IX, W).br("NEXT_ROW", "NEXT_ROW", "READ_ONE")
    f.at("NEXT_ROW").addc(IY, 1, IY)
    f.const(0).store(IX).go("READ_TEST")
    f.at("READ_ONE").inp().store(CHR)
    f.index(IX, IY, TMP)
    f.subc(CHR, 64).br("READ_NOT_AT", "READ_AT", "READ_NOT_AT")
    f.at("READ_AT").load(NMAN).store(MID)
    f.load(TMP).state_store(S_POS)
    for field in (S_DIR, S_A, S_B, S_HALT):
        f.const(0).state_store(field)
    f.addc(NMAN, 1, NMAN)
    # state_store uses CHR as its staging register; restore the known source.
    f.const(64).store(CHR).go("READ_WRITE")
    f.at("READ_NOT_AT").go("READ_WRITE")
    f.at("READ_WRITE").load(CHR).e("M").const(4).e("W", "{").cell_store(TMP)
    f.go("READ_ADV")
    f.at("READ_ADV").addc(IX, 1, IX).go("READ_ROW")

    # For each man, find its rectangular room and color that room. This doubles
    # as room discovery and avoids storing a separate topology table.
    f.at("AFTER_READ").const(0).store(MID).go("PREP_TEST")
    f.at("PREP_TEST").bin("-", MID, NMAN).br(
        "PREP_DONE", "PREP_DONE", "PREP_MAN"
    )
    f.at("PREP_MAN").state_load(S_POS).store(POS)
    f.load(POS).e("M").const(4).e("W", "}").store(IY)
    f.load(IY).e("M").const(4).e("W", "{", "M").load(POS).e("-").store(IX)
    f.load(IX).store(LEFT).go("LEFT_SCAN")

    f.at("LEFT_SCAN").subc(LEFT, 1, LEFT)
    f.index(LEFT, IY).raw(TMP).store(CH)
    f.eq(CH, 124, "LEFT_DONE", "LEFT_SCAN")
    f.at("LEFT_DONE").load(IX).store(RIGHT).go("RIGHT_SCAN")
    f.at("RIGHT_SCAN").addc(RIGHT, 1, RIGHT)
    f.index(RIGHT, IY).raw(TMP).store(CH)
    f.eq(CH, 124, "RIGHT_DONE", "RIGHT_SCAN")
    f.at("RIGHT_DONE").load(IY).store(TOP).go("TOP_SCAN")
    f.at("TOP_SCAN").subc(TOP, 1, TOP)
    f.index(LEFT, TOP).raw(TMP).store(CH)
    f.eq(CH, 43, "TOP_DONE", "TOP_SCAN")
    f.at("TOP_DONE").load(IY).store(BOTTOM).go("BOTTOM_SCAN")
    f.at("BOTTOM_SCAN").addc(BOTTOM, 1, BOTTOM)
    f.index(LEFT, BOTTOM).raw(TMP).store(CH)
    f.eq(CH, 43, "COLOR_ROOM_INIT", "BOTTOM_SCAN")

    f.at("COLOR_ROOM_INIT").load(TOP).store(IY)
    f.load(LEFT).store(IX).go("COLOR_ROOM_TEST")
    f.at("COLOR_ROOM_TEST").bin("-", IY, BOTTOM).br(
        "COLOR_ROOM_DONE", "COLOR_ROW", "COLOR_ROW"
    )
    f.at("COLOR_ROW").bin("-", IX, RIGHT).br(
        "COLOR_NEXT_ROW", "COLOR_CELL", "COLOR_CELL"
    )
    f.at("COLOR_NEXT_ROW").addc(IY, 1, IY)
    f.load(LEFT).store(IX).go("COLOR_ROOM_TEST")
    f.at("COLOR_CELL").index(IX, IY).raw(TMP).store(CH).go("COLOR_BOUND_X")
    for index, addr in enumerate((LEFT, RIGHT)):
        label = "COLOR_BOUND_X" if index == 0 else "COLOR_BOUND_X2"
        if label not in f.blocks:
            f.at(label)
        next_label = "COLOR_BOUND_X2" if index == 0 else "COLOR_BOUND_Y"
        f.bin("-", IX, addr).br(next_label, "COLOR_WALL", next_label)
    f.at("COLOR_BOUND_Y").bin("-", IY, TOP).br(
        "COLOR_BOUND_Y2", "COLOR_WALL", "COLOR_BOUND_Y2"
    )
    f.at("COLOR_BOUND_Y2").bin("-", IY, BOTTOM).br(
        "COLOR_INTERIOR", "COLOR_WALL", "COLOR_INTERIOR"
    )
    f.at("COLOR_INTERIOR")
    emit_color_dispatch(f)
    f.at("COLOR_WRITE").e("sp")
    f.load(CH).e("M").const(4).e("W", "{", "M", "rp", "+").cell_store(TMP)
    f.addc(IX, 1, IX).go("COLOR_ROOM_TEST")
    f.at("COLOR_ROOM_DONE").addc(MID, 1, MID).go("PREP_TEST")

    f.at("PREP_DONE").const(0).store(DEAD).go("DRAW_FULL")

    # Round/tick loop. Men act sequentially, which is equivalent for this
    # no-pipe slice; wall termination is observed after every man has acted.
    f.at("ROUND").inp().store(K).go("STEP_TEST")
    f.at("STEP_TEST").load(DEAD).br("DRAW_DELTA", "K_TEST", "DRAW_DELTA")
    f.at("K_TEST").load(K).br("TICK_START", "DRAW_DELTA", "DRAW_DELTA")
    f.at("TICK_START").const(0).store(MID).go("MAN_TEST")
    f.at("MAN_TEST").bin("-", MID, NMAN).br(
        "TICK_FINISH", "TICK_FINISH", "MAN_HALT"
    )
    f.at("MAN_HALT").state_load(S_HALT).store(HALT)
    f.load(HALT).br("MAN_NEXT", "MAN_LOAD", "MAN_NEXT")
    f.at("MAN_LOAD")
    for field, addr in (
        (S_POS, POS), (S_DIR, DIR), (S_A, RA), (S_B, RB)
    ):
        f.state_load(field).store(addr)
    f.cell_load(POS).raw().store(CH).go("DISPATCH")

    dispatch = [
        (94, "OP_N"), (62, "OP_E"), (118, "OP_S"), (60, "OP_W"),
        (77, "OP_M"), (43, "OP_ADD"), (45, "OP_SUB"), (88, "OP_X"), (72, "OP_H"),
    ]
    for index, (ascii_value, op_label) in enumerate(dispatch):
        here = "DISPATCH" if index == 0 else f"DISPATCH_{index}"
        if here not in f.blocks:
            f.at(here)
        next_label = (
            f"DISPATCH_{index + 1}" if index + 1 < len(dispatch) else "DIGIT_TEST"
        )
        f.subc(CH, ascii_value).br(next_label, op_label, next_label)
    f.at("DIGIT_TEST").subc(CH, 48).br("DIGIT_HI", "OP_DIGIT", "MOVE")
    f.at("DIGIT_HI").subc(CH, 57).br("MOVE", "OP_DIGIT", "OP_DIGIT")
    for label, direction in (
        ("OP_E", 0), ("OP_S", 1), ("OP_W", 2), ("OP_N", 3)
    ):
        f.at(label).const(direction).store(DIR).go("MOVE")
    f.at("OP_DIGIT").subc(CH, 48).store(RA).go("MOVE")
    f.at("OP_M").load(RA).store(RB).go("MOVE")
    f.at("OP_ADD").bin("+", RA, RB, RA).go("MOVE")
    f.at("OP_SUB").bin("-", RA, RB, RA).go("MOVE")
    f.at("OP_H").const(1).store(HALT).go("MAN_SAVE")
    f.at("OP_X").load(RA).br("X_POS", "MOVE", "X_NEG")
    f.at("X_POS").addc(DIR, 1).e("M").const(3).e("W", "&").store(DIR).go("MOVE")
    f.at("X_NEG").addc(DIR, 3).e("M").const(3).e("W", "&").store(DIR).go("MOVE")

    # Restore the old pixel in the display's preserved next buffer.
    f.at("MOVE").load(POS).e("sa")
    f.cell_load(POS).e("sp")
    f.const(8).e("M").const(7).e("+", "M", "rp", "&", "sd")
    f.load(DIR).br("DIR_NONZERO", "MOVE_E", "DIR_NONZERO")
    f.at("DIR_NONZERO").subc(DIR, 1).br("DIR_2PLUS", "MOVE_S", "DIR_2PLUS")
    f.at("DIR_2PLUS").subc(DIR, 2).br("MOVE_N", "MOVE_W", "MOVE_N")
    f.at("MOVE_E").addc(POS, 1, POS).go("MOVE_DRAW_NEW")
    f.at("MOVE_S").addc(POS, 16, POS).go("MOVE_DRAW_NEW")
    f.at("MOVE_W").subc(POS, 1, POS).go("MOVE_DRAW_NEW")
    f.at("MOVE_N").subc(POS, 16, POS).go("MOVE_DRAW_NEW")
    f.at("MOVE_DRAW_NEW").load(POS).e("sa")
    f.const(9).e("sd").go("WALL_TEST")
    f.at("WALL_TEST").cell_load(POS).e("sp")
    f.const(8).e("M").const(7).e("+", "M", "rp", "&").store(CH)
    f.subc(CH, 4).br("MAN_SAVE", "HIT_WALL", "MAN_SAVE")
    f.at("HIT_WALL").const(1).store(DEAD).go("MAN_SAVE")

    f.at("MAN_SAVE")
    for field, addr in (
        (S_HALT, HALT), (S_POS, POS), (S_DIR, DIR), (S_A, RA), (S_B, RB)
    ):
        f.load(addr).state_store(field)
    f.go("MAN_NEXT")
    f.at("MAN_NEXT").addc(MID, 1, MID).go("MAN_TEST")
    f.at("TICK_FINISH").subc(K, 1, K).go("STEP_TEST")

    # Initial full raster; later rounds preserve it and commit only movement deltas.
    f.at("DRAW_FULL").const(0).store(TMP).go("DRAW_TEST")
    f.at("DRAW_TEST").subc(TMP, 256).br("DRAW_SWAP", "DRAW_SWAP", "DRAW_CELL")
    f.at("DRAW_CELL").cell_load(TMP).e("sp")
    f.const(8).e("M").const(7).e("+", "M", "rp", "&").store(STAGE)
    f.go("DRAW_M0")
    for man in range(MAX_MEN):
        state_pos = STATE0 + man * STATE_STRIDE + S_POS
        here = "DRAW_M0" if man == 0 else f"DRAW_M{man}"
        if here not in f.blocks:
            f.at(here)
        next_label = f"DRAW_M{man + 1}" if man + 1 < MAX_MEN else "DRAW_BASE"
        f.load(state_pos).e("M").load(TMP).e("-").br(
            next_label, "DRAW_MAN", next_label
        )
    f.at("DRAW_MAN").const(9).e("sd").go("DRAW_ADV")
    f.at("DRAW_BASE").load(STAGE).e("sd").go("DRAW_ADV")
    f.at("DRAW_ADV").addc(TMP, 1, TMP).go("DRAW_TEST")
    f.at("DRAW_SWAP").const(1).e("ss").go("ROUND")
    f.at("DRAW_DELTA").const(1).e("ss").go("ROUND")
    return f


def build():
    return subset.build_program(build_flow(), RAM_N, display_addr=True)


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "multi-room.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
