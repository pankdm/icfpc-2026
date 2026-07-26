#!/usr/bin/env python3
"""Queue-free Pathfinder using sixteen unsigned 16-bit row words.

Unlike the four-i64 prototype, every RAM value is in 0..65535, which is safe
for stateflow's split RAM command encoding. Direction and row loops are dynamic
so the physical controller does not contain 64 unrolled update blocks.
"""

import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow


OPEN = 0
UNVIS = 16
FRONT = 32
NEXT = 48
PARENT = (64, 80, 96, 112)
I, ROBOT, FLAG, ROW, BIT, TMP, CAND, TAKE = range(128, 136)
SCALAR_SIZE = 136
RAM_N = SCALAR_SIZE
BANKED = False
PACKED_CELL = False


class Flow(stateflow.Flow):
    def literal(self, value):
        if value < 2048:
            return self.const(value)
        return self.e("`", *str(value), "`")

    def dyn_addr(self, base):
        return self.const(base).e("M").load(I).e("+")

    def dyn_load(self, base):
        return self.dyn_addr(base).loadv()

    def dyn_store(self, base):
        return (
            self.store(TMP).dyn_addr(base).e("M")
            .load(TMP).storev()
        )

    def bit_parts(self, index_addr, base):
        # BIT := 1 << (index & 15); ROW := base + (index >> 4).
        self.const(15).e("M").load(index_addr).e("&", "M")
        self.const(1).e("{").store(BIT)
        self.load(index_addr).e("M").const(4).e("W", "}").store(ROW)
        return self.const(base).e("M").load(ROW).e("+").store(ROW)

    def bit_test(self, index_addr, base):
        self.bit_parts(index_addr, base)
        return self.load(ROW).loadv().e("M").load(BIT).e("&")

    def bit_set(self, index_addr, base):
        self.bit_parts(index_addr, base)
        self.load(ROW).loadv().store(TMP)
        self.bin("|", TMP, BIT, TMP)
        return self.load(ROW).e("M").load(TMP).storev()

    def bit_remove(self, index_addr, base):
        self.bit_parts(index_addr, base)
        self.load(ROW).loadv().store(TMP)
        self.bin("~", TMP, BIT, TMP)
        return self.load(ROW).e("M").load(TMP).storev()

    def apply_candidate(self, parent_base):
        self.store(CAND)
        self.dyn_load(UNVIS).e("M").load(CAND).e("&").store(TAKE)
        self.dyn_load(UNVIS).e("M").load(TAKE).e("~").dyn_store(UNVIS)
        self.dyn_load(parent_base).e("M").load(TAKE).e("|").dyn_store(parent_base)
        return self.dyn_load(NEXT).e("M").load(TAKE).e("|").dyn_store(NEXT)


def loop_test(f, body, done):
    return f.subc(I, 16).br(done, done, body)


def build_flow():
    f = Flow()

    # Initial 16x16 field and display.
    f.at("START").const(0).store(I).go("SETUP_TEST")
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

    # Reset row arrays for one query.
    f.at("ROUND").inp().store(TMP).inp().e("M")
    f.const(4).e("W", "{", "M").load(TMP).e("+").store(FLAG)
    f.display_const(FLAG, 9).const(0).store(I).go("RESET_TEST")
    f.at("RESET_TEST")
    loop_test(f, "RESET_BODY", "RESET_BITS")
    f.at("RESET_BODY").dyn_load(OPEN).dyn_store(UNVIS)
    f.const(0).dyn_store(FRONT).dyn_store(NEXT)
    for base in PARENT:
        f.const(0).dyn_store(base)
    f.addc(I, 1, I).go("RESET_TEST")
    f.at("RESET_BITS").bit_set(FLAG, FRONT).bit_remove(FLAG, UNVIS).go("BFS_CHECK")

    f.at("BFS_CHECK").bit_test(ROBOT, FRONT).br("WALK", "CLEAR_START", "WALK")
    f.at("CLEAR_START").const(0).store(I).go("CLEAR_TEST")
    f.at("CLEAR_TEST")
    loop_test(f, "CLEAR_BODY", "U_START")
    f.at("CLEAR_BODY").const(0).dyn_store(NEXT).addc(I, 1, I).go("CLEAR_TEST")

    # U: destination row i receives frontier row i-1.
    f.at("U_START").const(0).store(I).go("U_TEST")
    f.at("U_TEST")
    loop_test(f, "U_BOUND", "R_START")
    f.at("U_BOUND").load(I).br("U_LOAD", "U_ZERO", "U_ZERO")
    f.at("U_ZERO").const(0).go("U_APPLY")
    f.at("U_LOAD").subc(I, 1, I).dyn_load(FRONT).store(CAND)
    f.addc(I, 1, I).load(CAND).go("U_APPLY")
    f.at("U_APPLY").apply_candidate(PARENT[0]).addc(I, 1, I).go("U_TEST")

    # R: previous frontier lies one cell to the right.
    f.at("R_START").const(0).store(I).go("R_TEST")
    f.at("R_TEST")
    loop_test(f, "R_BODY", "D_START")
    f.at("R_BODY").dyn_load(FRONT).e("M").const(1).e("W", "}").apply_candidate(PARENT[1])
    f.addc(I, 1, I).go("R_TEST")

    # D: destination row i receives frontier row i+1.
    f.at("D_START").const(0).store(I).go("D_TEST")
    f.at("D_TEST")
    loop_test(f, "D_BOUND", "L_START")
    f.at("D_BOUND").subc(I, 15).br("D_ZERO", "D_ZERO", "D_LOAD")
    f.at("D_ZERO").const(0).go("D_APPLY")
    f.at("D_LOAD").addc(I, 1, I).dyn_load(FRONT).store(CAND)
    f.subc(I, 1, I).load(CAND).go("D_APPLY")
    f.at("D_APPLY").apply_candidate(PARENT[2]).addc(I, 1, I).go("D_TEST")

    # L: shift within one unsigned 16-bit row.
    f.at("L_START").const(0).store(I).go("L_TEST")
    f.at("L_TEST")
    loop_test(f, "L_BODY", "COPY_START")
    f.at("L_BODY").dyn_load(FRONT).e("M").const(1).e("W", "{")
    f.e("M").literal(65535).e("&").apply_candidate(PARENT[3])
    f.addc(I, 1, I).go("L_TEST")

    f.at("COPY_START").const(0).store(I).go("COPY_TEST")
    f.at("COPY_TEST")
    loop_test(f, "COPY_BODY", "BFS_CHECK")
    f.at("COPY_BODY").dyn_load(NEXT).dyn_store(FRONT).addc(I, 1, I).go("COPY_TEST")

    # Reconstruct exact U/R/D/L parent chain and emit frames.
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


def build(scalar_belts=8, code_x=60):
    return stateflow.build_program(
        build_flow(),
        scalar_size=SCALAR_SIZE,
        scalar_belts=scalar_belts,
        code_x=code_x,
        pooled_edges=True,
        tight_gaps=True,
        dedup_edges=True,
        coalesce_targets=True,
        queue=False,
        fast_cell_ram=False,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--scalar-belts", type=int, default=8)
    parser.add_argument("--code-x", type=int, default=60)
    args = parser.parse_args()
    program = build(args.scalar_belts, args.code_x)
    output = os.path.join(HERE, f"wavefront16-s{args.scalar_belts}-x{args.code_x}.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
