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
DESC0 = 288
MAX_PIPES = 16
PIPE_RAM_N = DESC0 + MAX_PIPES
SEL_I, SEL_COUNT, SEL_BEST, SEL_BEST_DIST = range(304, 308)
SEL_CAND, SEL_MAN, SEL_DESC, SEL_ROOM = range(308, 312)
SEL_DX, SEL_DY, SEL_DIST = range(312, 315)
PIPE_IO_RAM_N = 320


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

    def cell_low(self, index_addr):
        return (
            self.cell_load(index_addr).e("sp")
            .const(15).e("M", "rp", "&")
        )

    def cell_ascii(self, index_addr):
        return (
            self.cell_load(index_addr).e("M")
            .const(4).e("W", "}", "sp")
            .const(127).e("M", "rp", "&")
        )

    def cell_field(self, index_addr, shift, mask):
        """Extract a packed field from a cell record."""
        return (
            self.cell_load(index_addr).e("sp")
            .const(shift).e("M", "rp", "}", "sp")
            .const(mask).e("M", "rp", "&")
        )

    def array_addr(self, base, index_addr):
        return (
            self.load(index_addr).e("sp")
            .const(base).e("M", "rp", "+")
        )

    def array_store(self, base, index_addr):
        return (
            self.store(STAGE).array_addr(base, index_addr)
            .e("M").load(STAGE).storev()
        )

    def store_far(self, addr):
        """Store A at a synthesized fixed address without requiring B."""
        return (
            self.e("sp")
            .const(1).e("sc")
            .const(addr).e("sc", "rp", "sc")
        )

    def load_far(self, addr):
        """Load a synthesized fixed address while preserving B."""
        return (
            self.e("W", "sp", "W")
            .const(0).e("sc")
            .const(addr).e("sc", "rr", "M", "rp", "W")
        )

    def far_field(self, addr, shift, mask):
        return (
            self.load_far(addr).e("sp")
            .const(shift).e("M", "rp", "}", "sp")
            .const(mask).e("M", "rp", "&")
        )

    def far_bin(self, op, left, right):
        return self.load_far(right).e("M").load_far(left).e(op)

    def array_addr_far(self, base, index_addr):
        return (
            self.load_far(index_addr).e("sp")
            .const(base).e("M", "rp", "+")
        )

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


def emit_color_dispatch(f, tag_walls=False):
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
    f.at("COLOR_WALL")
    if tag_walls:
        # Walls are never executed as instructions. Reuse their high bits to
        # identify the owning room from adjacent pipe endpoints.
        f.addc(MID, 1).e("sp")
        f.const(11).e("M", "rp", "{", "M").const(4).e("+")
        f.cell_store(TMP).go("COLOR_ADV")
    else:
        f.const(4).go("COLOR_WRITE")
    f.at("COLOR_DIGIT").const(8).go("COLOR_WRITE")
    f.at("COLOR_ZERO").const(0).go("COLOR_WRITE")
    for color in sorted(set(mapping.values())):
        f.at(f"COLOR_C{color}").const(color).go("COLOR_WRITE")


def emit_pipe_next(f, prefix, source_addr, result_addr, done_label):
    """Emit blocks computing the address after one target-pipe arrow."""
    f.at(prefix).cell_ascii(source_addr).store(CH).go(f"{prefix}_TEST_0")
    directions = ((62, 1), (118, 16), (60, -1), (94, -16))
    for index, (ascii_value, delta) in enumerate(directions):
        label = f"{prefix}_TEST_{index}"
        if label not in f.blocks:
            f.at(label)
        next_label = f"{prefix}_TEST_{index + 1}" if index < 3 else f"{prefix}_BAD"
        move_label = f"{prefix}_MOVE_{index}"
        f.subc(CH, ascii_value).br(next_label, move_label, next_label)
        f.at(move_label)
        if delta > 0:
            f.addc(source_addr, delta, result_addr)
        else:
            f.subc(source_addr, -delta, result_addr)
        f.go(done_label)
    f.at(f"{prefix}_BAD").const(1).store(DEAD).go(done_label)


def emit_pipe_backward(f, prefix, source_addr, result_addr, done_label):
    """Emit blocks computing the cell behind a source arrowhead."""
    f.at(prefix).cell_ascii(source_addr).store(CH).go(f"{prefix}_TEST_0")
    directions = ((62, -1), (118, -16), (60, 1), (94, 16))
    for index, (ascii_value, delta) in enumerate(directions):
        label = f"{prefix}_TEST_{index}"
        if label not in f.blocks:
            f.at(label)
        next_label = f"{prefix}_TEST_{index + 1}" if index < 3 else f"{prefix}_BAD"
        move_label = f"{prefix}_MOVE_{index}"
        f.subc(CH, ascii_value).br(next_label, move_label, next_label)
        f.at(move_label)
        if delta > 0:
            f.addc(source_addr, delta, result_addr)
        else:
            f.subc(source_addr, -delta, result_addr)
        f.go(done_label)
    f.at(f"{prefix}_BAD").const(1).store(DEAD).go(done_label)


def emit_endpoint_selection(f, prefix, incoming, success_label, none_label):
    """Select the nearest endpoint owned by MID's room.

    Ties resolve to the lowest row-major address, matching reading order.
    The selected address remains in SEL_BEST.
    """
    room_shift = 16 if incoming else 19
    address_shift = 0 if incoming else 8

    f.at(f"{prefix}_INIT").const(0).store_far(SEL_I)
    f.load(31).store_far(SEL_COUNT)
    f.const(1).e("N").store_far(SEL_BEST)
    f.const(1000).store_far(SEL_BEST_DIST)
    f.load(POS).store_far(SEL_MAN).go(f"{prefix}_TEST")

    f.at(f"{prefix}_TEST").far_bin("-", SEL_I, SEL_COUNT).br(
        f"{prefix}_DONE", f"{prefix}_DONE", f"{prefix}_DESC"
    )
    f.at(f"{prefix}_DESC").array_addr_far(DESC0, SEL_I).loadv()
    f.store_far(SEL_DESC)
    f.far_field(SEL_DESC, room_shift, 7).store_far(SEL_ROOM)
    f.addc(MID, 1).e("M").load_far(SEL_ROOM).e("-").br(
        f"{prefix}_NEXT", f"{prefix}_CAND", f"{prefix}_NEXT"
    )
    f.at(f"{prefix}_CAND").far_field(SEL_DESC, address_shift, 255)
    f.store_far(SEL_CAND)

    # dx = abs((man & 15) - (candidate & 15)).
    f.far_field(SEL_MAN, 0, 15).store_far(SEL_DX)
    f.far_field(SEL_CAND, 0, 15).store_far(SEL_DY)
    f.far_bin("-", SEL_DX, SEL_DY).br(
        f"{prefix}_DX_POS", f"{prefix}_DX_POS", f"{prefix}_DX_NEG"
    )
    f.at(f"{prefix}_DX_POS").store_far(SEL_DX).go(f"{prefix}_DY")
    f.at(f"{prefix}_DX_NEG").e("N").store_far(SEL_DX).go(f"{prefix}_DY")

    # dy = abs((man >> 4) - (candidate >> 4)).
    f.at(f"{prefix}_DY").far_field(SEL_MAN, 4, 15).store_far(SEL_DY)
    f.far_field(SEL_CAND, 4, 15).store_far(SEL_DIST)
    f.far_bin("-", SEL_DY, SEL_DIST).br(
        f"{prefix}_DY_POS", f"{prefix}_DY_POS", f"{prefix}_DY_NEG"
    )
    f.at(f"{prefix}_DY_POS").store_far(SEL_DY).go(f"{prefix}_DIST")
    f.at(f"{prefix}_DY_NEG").e("N").store_far(SEL_DY).go(f"{prefix}_DIST")
    f.at(f"{prefix}_DIST").far_bin("+", SEL_DX, SEL_DY)
    f.store_far(SEL_DIST)

    f.far_bin("-", SEL_DIST, SEL_BEST_DIST).br(
        f"{prefix}_NEXT", f"{prefix}_TIE", f"{prefix}_UPDATE"
    )
    f.at(f"{prefix}_TIE").far_bin("-", SEL_CAND, SEL_BEST).br(
        f"{prefix}_NEXT", f"{prefix}_NEXT", f"{prefix}_UPDATE"
    )
    f.at(f"{prefix}_UPDATE").load_far(SEL_DIST).store_far(SEL_BEST_DIST)
    f.load_far(SEL_CAND).store_far(SEL_BEST).go(f"{prefix}_NEXT")
    f.at(f"{prefix}_NEXT").load_far(SEL_I).e("M").const(1).e("+")
    f.store_far(SEL_I).go(f"{prefix}_TEST")

    f.at(f"{prefix}_DONE").load_far(SEL_BEST).br(
        success_label, success_label, none_label
    )


def build_flow(enable_pipes=False, enable_io=False):
    if enable_io:
        enable_pipes = True
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
    f.at("READ_WRITE")
    if enable_pipes:
        f.go("READ_PIPE_TEST")
        pipe_glyphs = (62, 118, 60, 94, 45, 124)
        for index, ascii_value in enumerate(pipe_glyphs):
            here = "READ_PIPE_TEST" if index == 0 else f"READ_PIPE_TEST_{index}"
            if here not in f.blocks:
                f.at(here)
            next_label = (
                f"READ_PIPE_TEST_{index + 1}"
                if index + 1 < len(pipe_glyphs)
                else "READ_NORMAL_REC"
            )
            f.subc(CHR, ascii_value).br(next_label, "READ_PIPE_REC", next_label)
        f.at("READ_PIPE_REC").load(CHR).e("M").const(4).e(
            "W", "{", "M"
        ).const(6).e("+").cell_store(TMP).go("READ_ADV")
        f.at("READ_NORMAL_REC").load(CHR).e("M").const(4).e(
            "W", "{"
        ).cell_store(TMP).go("READ_ADV")
    else:
        f.load(CHR).e("M").const(4).e("W", "{").cell_store(TMP)
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
    emit_color_dispatch(f, tag_walls=enable_pipes)
    f.at("COLOR_WRITE").e("sp")
    f.load(CH).e("M").const(4).e("W", "{", "M", "rp", "+").cell_store(TMP)
    if enable_pipes:
        f.go("COLOR_ADV")
        f.at("COLOR_ADV").addc(IX, 1, IX).go("COLOR_ROOM_TEST")
    else:
        f.addc(IX, 1, IX).go("COLOR_ROOM_TEST")
    f.at("COLOR_ROOM_DONE").addc(MID, 1, MID).go("PREP_TEST")

    f.at("PREP_DONE")
    if enable_pipes:
        f.go("PIPE_SCAN_INIT")
    else:
        f.const(0).store(DEAD).go("DRAW_FULL")

    if enable_pipes:
        # Phase aliases: LEFT=count, RIGHT=scan, POS=current, DIR=predecessor,
        # TMP=downstream, TOP=destination, BOTTOM=source. NMAN remains live.
        p_count, p_scan, p_cur, p_pred = LEFT, RIGHT, POS, DIR
        p_next, p_dest, p_source = TMP, TOP, BOTTOM

        f.at("PIPE_SCAN_INIT").const(0).store(p_count)
        f.const(0).store(p_scan).go("PIPE_SCAN_TEST")
        f.at("PIPE_SCAN_TEST").subc(p_scan, 256).br(
            "PIPE_SCAN_DONE", "PIPE_SCAN_DONE", "PIPE_SCAN_CELL"
        )
        f.at("PIPE_SCAN_CELL").cell_low(p_scan).store(CH)
        f.subc(CH, 6).br("PIPE_SCAN_ADV", "PIPE_DEST_NEXT", "PIPE_SCAN_ADV")
        emit_pipe_next(
            f, "PIPE_DEST_NEXT", p_scan, p_next, "PIPE_DEST_WALL_TEST"
        )
        f.at("PIPE_DEST_WALL_TEST").cell_low(p_next).store(CH)
        f.subc(CH, 4).br("PIPE_SCAN_ADV", "PIPE_DEST_FOUND", "PIPE_SCAN_ADV")
        f.at("PIPE_DEST_FOUND").load(p_scan).store(p_dest)
        f.cell_field(p_next, 11, 7).e("sp")
        f.const(16).e("M", "rp", "{", "M").load(p_dest).e("+")
        f.array_store(DESC0, p_count)
        f.load(p_scan).store(p_cur).go("PIPE_PRED_0")

        candidate_deltas = (-1, 1, -16, 16)
        for candidate_index, delta in enumerate(candidate_deltas):
            candidate_label = f"PIPE_PRED_{candidate_index}"
            if candidate_label not in f.blocks:
                f.at(candidate_label)
            if delta > 0:
                f.addc(p_cur, delta, p_pred)
            else:
                f.subc(p_cur, -delta, p_pred)
            f.cell_low(p_pred).store(CH)
            next_candidate = (
                f"PIPE_PRED_{candidate_index + 1}"
                if candidate_index + 1 < len(candidate_deltas)
                else "PIPE_SOURCE_FOUND"
            )
            neighbor_label = f"PIPE_PRED_NEIGHBOR_{candidate_index}"
            f.subc(CH, 6).br(next_candidate, neighbor_label, next_candidate)
            f.at(neighbor_label).bin("-", p_pred, p_next).br(
                "PIPE_PRED_FOUND", next_candidate, "PIPE_PRED_FOUND"
            )

        f.at("PIPE_PRED_FOUND").cell_load(p_cur).store(STAGE)
        f.addc(p_pred, 1).e("sp")
        f.const(11).e("M", "rp", "{", "M").load(STAGE).e("+").cell_store(p_cur)
        f.load(p_cur).store(p_next)
        f.load(p_pred).store(p_cur).go("PIPE_PRED_0")

        # Descriptor packs destination/source addresses in bits 0..15 and their
        # one-based room IDs in bits 16..18 / 19..21.
        f.at("PIPE_SOURCE_FOUND").load(p_cur).store(p_source).go("PIPE_SOURCE_BACK")
        emit_pipe_backward(
            f, "PIPE_SOURCE_BACK", p_source, p_pred, "PIPE_SOURCE_FINAL"
        )
        f.at("PIPE_SOURCE_FINAL").array_addr(DESC0, p_count).loadv().store(STAGE)
        f.cell_field(p_pred, 11, 7).e("sp")
        f.const(19).e("M", "rp", "{", "sp")
        f.load(p_source).e("M").const(8).e("W", "{", "sp")
        f.load(STAGE).e("M", "rp", "+", "M", "rp", "+")
        f.array_store(DESC0, p_count)
        f.addc(p_count, 1, p_count).go("PIPE_SCAN_ADV")

        f.at("PIPE_SCAN_ADV").addc(p_scan, 1, p_scan).go("PIPE_SCAN_TEST")
        f.at("PIPE_SCAN_DONE").load(p_count).store_far(31)
        f.const(0).store(DEAD).go("DRAW_FULL")

        # Pipe phase aliases: RA=count, MID=pipe index, RB=value code,
        # POS=current cell, DIR=predecessor. Values move destination-to-source,
        # matching the judge's reverse-index cascade.
        f.at("PIPE_SHIFT_INIT").load(31).store(RA)
        f.const(0).store(MID).go("PIPE_SHIFT_TEST")
        f.at("PIPE_SHIFT_TEST").bin("-", MID, RA).br(
            "PIPE_SHIFT_DONE", "PIPE_SHIFT_DONE", "PIPE_SHIFT_DESC"
        )
        f.at("PIPE_SHIFT_DESC").array_addr(DESC0, MID).loadv().e("sp")
        f.const(255).e("M", "rp", "&").store(POS).go("PIPE_SHIFT_CELL")

        f.at("PIPE_SHIFT_CELL").cell_field(POS, 11, 511).store(DIR)
        f.load(DIR).br("PIPE_SHIFT_HAVE_PRED", "PIPE_SHIFT_NEXT", "PIPE_SHIFT_NEXT")
        f.at("PIPE_SHIFT_HAVE_PRED").subc(DIR, 1, DIR)
        f.cell_field(POS, 20, 31).store(RB)
        f.load(RB).br("PIPE_SHIFT_ADV", "PIPE_SHIFT_PRED_VALUE", "PIPE_SHIFT_ADV")
        f.at("PIPE_SHIFT_PRED_VALUE").cell_field(DIR, 20, 31).store(RB)
        f.load(RB).br("PIPE_SHIFT_MOVE", "PIPE_SHIFT_ADV", "PIPE_SHIFT_ADV")

        f.at("PIPE_SHIFT_MOVE").cell_load(POS).store(STAGE)
        f.load(RB).e("sp")
        f.const(20).e("M", "rp", "{", "M").load(STAGE).e("+", "M")
        f.const(8).e("+").cell_store(POS)
        f.cell_load(DIR).store(STAGE)
        f.load(RB).e("sp")
        f.const(20).e("M", "rp", "{", "M").const(8).e("+", "M")
        f.load(STAGE).e("-").cell_store(DIR)
        f.load(POS).e("sa")
        f.const(14).e("sd")
        f.load(DIR).e("sa")
        f.const(6).e("sd").go("PIPE_SHIFT_ADV")

        f.at("PIPE_SHIFT_ADV").load(DIR).store(POS).go("PIPE_SHIFT_CELL")
        f.at("PIPE_SHIFT_NEXT").addc(MID, 1, MID).go("PIPE_SHIFT_TEST")
        f.at("PIPE_SHIFT_DONE").const(0).store(MID).go("MAN_TEST")

    # Round/tick loop. Men act sequentially, which is equivalent for this
    # no-pipe slice; wall termination is observed after every man has acted.
    f.at("ROUND").inp().store(K).go("STEP_TEST")
    f.at("STEP_TEST").load(DEAD).br("DRAW_DELTA", "K_TEST", "DRAW_DELTA")
    f.at("K_TEST").load(K).br("TICK_START", "DRAW_DELTA", "DRAW_DELTA")
    f.at("TICK_START")
    if enable_pipes:
        f.go("PIPE_SHIFT_INIT")
    else:
        f.const(0).store(MID).go("MAN_TEST")
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
    if enable_io:
        dispatch += [(115, "OP_SEND"), (114, "OP_RECV")]
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

    if enable_io:
        f.at("OP_SEND").go("SELECT_SEND_INIT")
        f.at("SEND_SELECTED").load_far(SEL_BEST).store(DIR)
        f.cell_field(DIR, 20, 31).br("PIPE_IO_BLOCK", "SEND_WRITE", "PIPE_IO_BLOCK")
        f.at("SEND_WRITE").cell_load(DIR).store(STAGE)
        f.addc(RA, 10).e("sp")
        f.const(20).e("M", "rp", "{", "M").load(STAGE).e("+", "M")
        f.const(8).e("+").cell_store(DIR)
        f.load(DIR).e("sa")
        f.const(14).e("sd").go("PIPE_IO_MOVE")

        f.at("OP_RECV").go("SELECT_RECV_INIT")
        f.at("RECV_SELECTED").load_far(SEL_BEST).store(DIR)
        f.cell_field(DIR, 20, 31).store_far(SEL_DIST)
        f.load_far(SEL_DIST).br("RECV_READ", "PIPE_IO_BLOCK", "PIPE_IO_BLOCK")
        f.at("RECV_READ").cell_load(DIR).store(STAGE)
        f.load_far(SEL_DIST).e("sp")
        f.const(20).e("M", "rp", "{", "M").const(8).e("+", "M")
        f.load(STAGE).e("-").cell_store(DIR)
        f.load_far(SEL_DIST).e("sp")
        f.const(10).e("M", "rp", "-").store(RA)
        f.load(DIR).e("sa")
        f.const(6).e("sd").go("PIPE_IO_MOVE")

        f.at("PIPE_IO_BLOCK").state_load(S_DIR).store(DIR).go("MAN_SAVE")
        f.at("PIPE_IO_MOVE").state_load(S_DIR).store(DIR).go("MOVE")

        emit_endpoint_selection(
            f, "SELECT_SEND", incoming=False,
            success_label="SEND_SELECTED", none_label="PIPE_IO_BLOCK"
        )
        emit_endpoint_selection(
            f, "SELECT_RECV", incoming=True,
            success_label="RECV_SELECTED", none_label="PIPE_IO_BLOCK"
        )

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
