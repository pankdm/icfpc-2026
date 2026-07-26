#!/usr/bin/env python3
"""Pathfinder with a 256-bit visited set and distance-carrying BFS queue.

The banked cell RAM is write-only during BFS: four scalar words reject walls
and revisits, while each queue item carries its own distance. Cell records are
retained only for the final greedy shortest-path walk.
"""

import argparse
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow


I, ROBOT, FLAG, EPOCH, CUR, REC, DIST, NEI = range(8)
TMP, TMP2, X, Y, QVAL, Q_EPOCH, WORD, BIT = range(8, 16)
WALL_BASE = 16
VIS_BASE = 20
SCALAR_RAM_N = 32
RAM_N = 288
CELL0 = 32
BANKED = True
PACKED_CELL = True
BYTE_MASK = 255


class Flow(stateflow.Flow):
    def cell_loadv(self):
        return self.e("cc", "cr")

    def cell_storev(self):
        return self.e("sp", "W", "M").const(1).e(
            "W", "+", "N", "cc", "rp", "cc"
        )

    def low_byte(self, addr, dst):
        return self.load(addr).e("sp").const(BYTE_MASK).e(
            "M", "rp", "&"
        ).store(dst)

    def high_epoch8(self, addr, dst):
        return self.load(addr).e("M").const(8).e("W", "}").store(dst)

    def queue_epoch(self, addr, dst):
        return self.const(16).e("M").load(addr).e("}").store(dst)

    def queue_distance(self, addr, dst):
        return (
            self.load(addr).e("M").const(8).e("W", "}")
            .e("sp").const(BYTE_MASK).e("M", "rp", "&").store(dst)
        )

    def epoch_base8(self, dst):
        return self.load(EPOCH).e("M").const(8).e("W", "{").store(dst)

    def epoch_base16(self, dst):
        return self.const(16).e("M").load(EPOCH).e("{").store(dst)

    def bit_parts(self, index_addr, base):
        # BIT := 1 << (index & 63)
        self.const(63).e("M").load(index_addr).e("&", "M")
        self.const(1).e("{").store(BIT)
        # WORD := base + (index >> 6)
        self.load(index_addr).e("M").const(6).e("W", "}").store(WORD)
        self.const(base).e("M")
        return self.load(WORD).e("+").store(WORD)

    def bit_test(self, index_addr, base):
        self.bit_parts(index_addr, base)
        self.load(WORD).loadv().store(TMP2)
        return self.bin("&", TMP2, BIT)

    def bit_set(self, index_addr, base):
        self.bit_parts(index_addr, base)
        self.load(WORD).loadv().store(TMP2)
        self.bin("|", TMP2, BIT, TMP2)
        return self.load(WORD).e("M").load(TMP2).storev()

    def queue_record(self, index_addr, distance_addr):
        self.epoch_base16(TMP)
        self.load(distance_addr).e("M").const(8).e("W", "{")
        self.e("M").load(TMP).e("+", "M").load(index_addr).e("+")
        return self.queue_push()


def signed_add(f, source, delta, dst):
    return f.addc(source, delta, dst) if delta >= 0 else f.subc(source, -delta, dst)


def emit_enqueue(f, prefix, delta, next_label):
    wall_clear = f"{prefix}_WALL_CLEAR"
    enqueue = f"{prefix}_ENQUEUE"
    linked = f"{prefix}_LINKED"
    f.at(f"{prefix}_TEST")
    signed_add(f, CUR, delta, NEI)
    f.bit_test(NEI, WALL_BASE).br(next_label, wall_clear, next_label)
    f.at(wall_clear).bit_test(NEI, VIS_BASE).br(next_label, enqueue, next_label)
    f.at(enqueue).bit_set(NEI, VIS_BASE)
    f.addc(DIST, 1, TMP2)
    f.epoch_base8(TMP).bin("+", TMP, TMP2).cell_store(NEI, REC)
    f.queue_record(NEI, TMP2)
    f.bin("-", NEI, ROBOT).br(linked, "BFS_DONE", linked)
    f.at(linked).go(next_label)


def emit_walk_choice(f, prefix, delta, next_label):
    candidate = f"{prefix}_CANDIDATE"
    compare = f"{prefix}_COMPARE"
    choose = f"{prefix}_CHOOSE"
    f.at(f"{prefix}_TEST")
    signed_add(f, CUR, delta, NEI)
    f.cell_load(NEI).store(REC).br(candidate, next_label, next_label)
    f.at(candidate).high_epoch8(REC, TMP2)
    f.bin("-", TMP2, EPOCH).br(next_label, compare, next_label)
    f.at(compare).low_byte(REC, TMP2)
    f.bin("-", TMP2, DIST).br(next_label, choose, next_label)
    f.at(choose).go("MOVE")


def build_flow():
    f = Flow()
    f.at("START").const(0).store(I).const(0).store(EPOCH).go("SETUP_TEST")
    f.at("SETUP_TEST").subc(I, 256).br(
        "SETUP_POSITION", "SETUP_POSITION", "SETUP_CELL"
    )
    f.at("SETUP_CELL").inp().br("SETUP_WALL", "SETUP_PATH", "SETUP_WALL")
    f.at("SETUP_WALL").bit_set(I, WALL_BASE)
    f.const(7).e("sd").go("SETUP_ADV")
    f.at("SETUP_PATH").const(0).e("sd").go("SETUP_ADV")
    f.at("SETUP_ADV").addc(I, 1, I).go("SETUP_TEST")
    f.at("SETUP_POSITION").inp().store(X).inp().store(Y).index(X, Y, ROBOT)
    f.display_const(ROBOT, 10).commit().go("ROUND")

    f.at("ROUND").inp().store(X).inp().store(Y).index(X, Y, FLAG)
    f.display_const(FLAG, 9).addc(EPOCH, 1, EPOCH)
    for addr in range(VIS_BASE, VIS_BASE + 4):
        f.const(0).store(addr)
    f.go("BFS_INIT")

    f.at("BFS_INIT").bit_set(FLAG, VIS_BASE)
    f.const(1).store(DIST)
    f.epoch_base8(TMP).addc(TMP, 1, TMP2)
    f.load(TMP2).cell_store(FLAG, REC)
    f.queue_record(FLAG, DIST).go("BFS_POP")

    f.at("BFS_POP").queue_pop().store(QVAL).queue_epoch(QVAL, Q_EPOCH)
    f.bin("-", Q_EPOCH, EPOCH).br("BFS_POP", "BFS_CURRENT", "BFS_POP")
    f.at("BFS_CURRENT").low_byte(QVAL, CUR).queue_distance(QVAL, DIST)
    f.go("BFS_UP_TEST")

    emit_enqueue(f, "BFS_UP", -16, "BFS_RIGHT_TEST")
    emit_enqueue(f, "BFS_RIGHT", 1, "BFS_DOWN_TEST")
    emit_enqueue(f, "BFS_DOWN", 16, "BFS_LEFT_TEST")
    emit_enqueue(f, "BFS_LEFT", -1, "BFS_POP")

    f.at("BFS_DONE").go("WALK")
    f.at("WALK").load(ROBOT).store(CUR)
    f.cell_load(CUR).store(REC).low_byte(REC, TMP2)
    f.subc(TMP2, 1, DIST).go("WALK_UP_TEST")
    emit_walk_choice(f, "WALK_UP", -16, "WALK_RIGHT_TEST")
    emit_walk_choice(f, "WALK_RIGHT", 1, "WALK_DOWN_TEST")
    emit_walk_choice(f, "WALK_DOWN", 16, "WALK_LEFT_TEST")
    emit_walk_choice(f, "WALK_LEFT", -1, "NO_PATH")

    f.at("MOVE").display_const(ROBOT, 0)
    f.load(NEI).store(ROBOT)
    f.display_const(ROBOT, 10).commit()
    f.bin("-", ROBOT, FLAG).br("WALK", "ROUND", "WALK")
    f.at("NO_PATH").e("H")
    return f


def build(belt_count=9):
    return stateflow.build_program(
        build_flow(),
        scalar_size=SCALAR_RAM_N,
        queue=True,
        fast_cell_ram=True,
        cell_belts=belt_count,
        packed_cell=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--belts", type=int, default=9)
    args = parser.parse_args()
    program = build(args.belts)
    output = os.path.join(HERE, f"reverse-bfs-bitset-b{args.belts}.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
