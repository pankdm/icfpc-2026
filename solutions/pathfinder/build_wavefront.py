#!/usr/bin/env python3
"""Four-word parallel-wavefront Pathfinder.

WIP: this first physical lowering deliberately reuses stateflow's scalar
service.  The algorithm is proven by verify_wavefront.py, but this lowering is
not yet gradeable: large mask literals can cross controller rows, and nested
scratch-preserving scalar macros currently corrupt the first expansion.  Do not
submit its output.  It exists to make the remaining lowering work explicit
before replacing the service with four parallel word lanes.
"""

import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow


I, ROBOT, FLAG, WORD, BIT, TMP, CAND, TAKE = range(8)
OPEN = 8
UNVIS = 12
FRONT = 16
PARENT = (20, 24, 28, 32)  # U/R/D/L
NEXT = 36
SCALAR_SIZE = 40
RAM_N = SCALAR_SIZE
BANKED = False
PACKED_CELL = False
WORD_MASK = (1 << 64) - 1
ROW_MASK = (1 << 16) - 1
COL0 = sum(1 << (16 * row) for row in range(4))
COL15 = COL0 << 15


class Flow(stateflow.Flow):
    def literal(self, value):
        value &= WORD_MASK
        if value >= 1 << 63:
            value -= 1 << 64
        if -9 <= value <= 9:
            return self.const(value) if value >= 0 else self.const(-value).e("N")
        if value < 0:
            return self.literal(-value).e("N")
        return self.e("`", *str(value), "`")

    def shift(self, addr, amount, left=True):
        return self.load(addr).e("M").const(amount).e("W", "{" if left else "}")

    def masked(self, mask):
        # A &= mask, preserving neither prior register.
        return self.e("M").literal(mask).e("&")

    def or_saved(self):
        # A is the second term; the first is waiting in scratch.
        return self.e("M", "rp", "|")

    def bit_parts(self, index_addr, base):
        self.const(63).e("M").load(index_addr).e("&", "M")
        self.const(1).e("{").store(BIT)
        self.load(index_addr).e("M").const(6).e("W", "}").store(WORD)
        return self.const(base).e("M").load(WORD).e("+").store(WORD)

    def bit_test(self, index_addr, base):
        self.bit_parts(index_addr, base)
        return self.load(WORD).loadv().e("M").load(BIT).e("&")

    def bit_set(self, index_addr, base):
        self.bit_parts(index_addr, base)
        self.load(WORD).loadv().store(TMP)
        self.bin("|", TMP, BIT, TMP)
        return self.load(WORD).e("M").load(TMP).storev()

    def bit_remove(self, index_addr, base):
        self.bit_parts(index_addr, base)
        self.load(WORD).loadv().store(TMP)
        # The bit is known to be present, so XOR is set subtraction.
        self.bin("~", TMP, BIT, TMP)
        return self.load(WORD).e("M").load(TMP).storev()


def contribution(f, direction, word):
    """Leave one directional contribution for destination word `word` in A."""
    if direction == 0:  # U parent: previous frontier is immediately above
        f.shift(FRONT + word, 16, left=True)
        if word:
            f.store(TMP).shift(FRONT + word - 1, 48, left=False)
            f.e("M").load(TMP).e("|")
        return f
    if direction == 1:  # R parent
        return f.shift(FRONT + word, 1, left=False).masked(WORD_MASK ^ COL15)
    if direction == 2:  # D parent
        f.shift(FRONT + word, 16, left=False)
        if word < 3:
            f.store(TMP).load(FRONT + word + 1).masked(ROW_MASK)
            f.e("M").const(48).e("W", "{")
            f.e("M").load(TMP).e("|")
        return f
    return f.shift(FRONT + word, 1, left=True).masked(WORD_MASK ^ COL0)


def apply_direction(f, direction, word):
    contribution(f, direction, word).store(CAND)
    f.bin("&", CAND, UNVIS + word, TAKE)
    f.bin("~", UNVIS + word, TAKE, UNVIS + word)
    f.bin("|", PARENT[direction] + word, TAKE, PARENT[direction] + word)
    return f.bin("|", NEXT + word, TAKE, NEXT + word)


def build_flow():
    f = Flow()
    f.at("START").const(0).store(I)
    for word in range(4):
        f.const(0).store(OPEN + word)
    f.go("SETUP_TEST")

    f.at("SETUP_TEST").subc(I, 256).br(
        "SETUP_POSITION", "SETUP_POSITION", "SETUP_CELL"
    )
    f.at("SETUP_CELL").inp().br("SETUP_WALL", "SETUP_OPEN", "SETUP_WALL")
    f.at("SETUP_OPEN").bit_set(I, OPEN).const(0).e("sd").go("SETUP_ADV")
    f.at("SETUP_WALL").const(7).e("sd").go("SETUP_ADV")
    f.at("SETUP_ADV").addc(I, 1, I).go("SETUP_TEST")

    f.at("SETUP_POSITION").inp().store(TMP).inp().e("M")
    f.const(4).e("W", "{", "M").load(TMP).e("+").store(ROBOT)
    f.display_const(ROBOT, 10).commit().go("ROUND")

    f.at("ROUND").inp().store(TMP).inp().e("M")
    f.const(4).e("W", "{", "M").load(TMP).e("+").store(FLAG)
    f.display_const(FLAG, 9)
    for word in range(4):
        f.load(OPEN + word).store(UNVIS + word)
        f.const(0).store(FRONT + word).store(NEXT + word)
        for base in PARENT:
            f.const(0).store(base + word)
    f.bit_set(FLAG, FRONT).bit_remove(FLAG, UNVIS).go("BFS_CHECK")

    f.at("BFS_CHECK").bit_test(ROBOT, FRONT).br("WALK", "BFS_CLEAR", "WALK")
    f.at("BFS_CLEAR")
    for word in range(4):
        f.const(0).store(NEXT + word)
    for direction in range(4):
        for word in range(4):
            apply_direction(f, direction, word)
    for word in range(4):
        f.load(NEXT + word).store(FRONT + word)
    f.go("BFS_CHECK")

    f.at("WALK").bin("-", ROBOT, FLAG).br("WALK_U", "ROUND", "WALK_U")
    for direction, label in enumerate(("U", "R", "D", "L")):
        next_label = ("WALK_R", "WALK_D", "WALK_L", "NO_PATH")[direction]
        f.at(f"WALK_{label}").bit_test(ROBOT, PARENT[direction]).br(
            f"MOVE_{label}", next_label, next_label
        )
        f.at(f"MOVE_{label}").display_const(ROBOT, 0)
        delta = (-16, 1, 16, -1)[direction]
        (f.addc if delta >= 0 else f.subc)(ROBOT, abs(delta), ROBOT)
        f.display_const(ROBOT, 10).commit().go("WALK")
    f.at("NO_PATH").e("H")
    return f


def build():
    return stateflow.build_program(
        build_flow(),
        scalar_size=SCALAR_SIZE,
        scalar_belts=5,
        code_x=60,
        pooled_edges=True,
        tight_gaps=True,
        dedup_edges=True,
        coalesce_targets=True,
        queue=False,
        fast_cell_ram=False,
    )


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "wavefront-v1.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
