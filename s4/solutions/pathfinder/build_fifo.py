#!/usr/bin/env python3
"""Generate Pathfinder with an epoch-tagged cell map and physical pipe FIFO."""

import os
import sys
import argparse

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow


I, ROBOT, FLAG, EPOCH, CUR, REC, DIST, NEI = range(8)
TMP, TMP2, X, Y, QVAL, Q_EPOCH = range(8, 14)
SCALAR_RAM_N = 32
RAM_N = 288
CELL0 = 32
BANKED = True
PACKED_CELL = True
BYTE_MASK = 255


class Flow(stateflow.Flow):
    def cell_loadv(self):
        """A := cell[A] through one atomic packed request."""
        return self.e("cc", "cr")

    def cell_storev(self):
        """cell[B] := A through a negative address marker and value."""
        return (
            self.e("sp", "W", "M").const(1).e("W", "+", "N", "cc", "rp", "cc")
        )

    def low_byte(self, addr, dst):
        return (
            self.load(addr).e("sp")
            .const(BYTE_MASK).e("M", "rp", "&").store(dst)
        )

    def high_epoch(self, addr, dst):
        return (
            self.load(addr).e("M").const(8).e("W", "}").store(dst)
        )

    def epoch_base(self, dst):
        return (
            self.load(EPOCH).e("M").const(8).e("W", "{").store(dst)
        )


def signed_add(f, source, delta, dst):
    return (
        f.addc(source, delta, dst) if delta >= 0
        else f.subc(source, -delta, dst)
    )


def emit_enqueue(f, prefix, delta, next_label):
    test = f"{prefix}_TEST"
    positive = f"{prefix}_POSITIVE"
    enqueue = f"{prefix}_ENQUEUE"
    linked = f"{prefix}_LINKED"
    f.at(test)
    signed_add(f, CUR, delta, NEI)
    f.cell_load(NEI).store(REC).br(positive, enqueue, next_label)
    # Positive records from this epoch are already visited; older epochs are
    # logically unvisited and may be overwritten without a clear pass.
    f.at(positive).high_epoch(REC, TMP2)
    f.bin("-", TMP2, EPOCH).br(enqueue, next_label, enqueue)
    f.at(enqueue)
    f.epoch_base(TMP).addc(DIST, 1, TMP2)
    f.bin("+", TMP, TMP2).cell_store(NEI, TMP)
    f.epoch_base(TMP).bin("+", TMP, NEI).queue_push()
    f.bin("-", NEI, ROBOT).br(linked, "BFS_DONE", linked)
    f.at(linked).go(next_label)
    return test


def emit_walk_choice(f, prefix, delta, next_label):
    test = f"{prefix}_TEST"
    candidate = f"{prefix}_CANDIDATE"
    choose = f"{prefix}_CHOOSE"
    f.at(test)
    signed_add(f, CUR, delta, NEI)
    f.cell_load(NEI).store(REC).br(candidate, next_label, next_label)
    f.at(candidate).high_epoch(REC, TMP2)
    f.bin("-", TMP2, EPOCH).br(next_label, "WALK_DISTANCE", next_label)
    # This shared block cannot be used by multiple candidates because NEI and
    # REC carry the candidate dynamically. It returns through a per-candidate
    # comparison block.
    compare = f"{prefix}_COMPARE"
    # Replace the temporary shared target with the local comparison below.
    f.blocks[candidate][-1] = ("br", next_label, compare, next_label)
    f.at(compare).low_byte(REC, TMP2)
    f.bin("-", TMP2, DIST).br(next_label, choose, next_label)
    f.at(choose).go("MOVE")
    return test


def build_flow():
    f = Flow()
    f.at("START").const(0).store(I).const(0).store(EPOCH).go("SETUP_TEST")
    f.at("SETUP_TEST").subc(I, 256).br(
        "SETUP_POSITION", "SETUP_POSITION", "SETUP_CELL"
    )
    f.at("SETUP_CELL").inp().br("SETUP_WALL", "SETUP_PATH", "SETUP_WALL")
    f.at("SETUP_WALL").const(1).e("N").cell_store(I, TMP)
    f.const(7).e("sd").go("SETUP_ADV")
    f.at("SETUP_PATH").const(0).e("sd").go("SETUP_ADV")
    f.at("SETUP_ADV").addc(I, 1, I).go("SETUP_TEST")
    f.at("SETUP_POSITION").inp().store(X).inp().store(Y).index(X, Y, ROBOT)
    f.display_const(ROBOT, 10).commit().go("ROUND")

    f.at("ROUND").inp().store(X).inp().store(Y).index(X, Y, FLAG)
    f.display_const(FLAG, 9)
    f.addc(EPOCH, 1, EPOCH).go("BFS_INIT")

    # Seed flag record (layer 1) and queue item (epoch | index).
    f.at("BFS_INIT").epoch_base(TMP).addc(TMP, 1, TMP2)
    f.load(TMP2).cell_store(FLAG, TMP)
    f.epoch_base(TMP).bin("+", TMP, FLAG).queue_push().go("BFS_POP")

    # Old frontier values may remain after the previous BFS stopped on robot
    # discovery. Epoch filtering drains them before reaching the new flag.
    f.at("BFS_POP").queue_pop().store(QVAL).high_epoch(QVAL, Q_EPOCH)
    f.bin("-", Q_EPOCH, EPOCH).br("BFS_POP", "BFS_CURRENT", "BFS_POP")
    f.at("BFS_CURRENT").low_byte(QVAL, CUR)
    f.cell_load(CUR).store(REC).low_byte(REC, DIST).go("BFS_UP_TEST")

    emit_enqueue(f, "BFS_UP", -16, "BFS_RIGHT_TEST")
    emit_enqueue(f, "BFS_RIGHT", 1, "BFS_DOWN_TEST")
    emit_enqueue(f, "BFS_DOWN", 16, "BFS_LEFT_TEST")
    emit_enqueue(f, "BFS_LEFT", -1, "BFS_POP")

    # Descend current-epoch distances from robot to flag in required order.
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


def build(belt_count=9, code_x=60, scalar_belts=1):
    return stateflow.build_program(
        build_flow(),
        scalar_size=SCALAR_RAM_N,
        scalar_belts=scalar_belts,
        fast_scalar_ram=scalar_belts > 1,
        scalar_command_band=2,
        scalar_reply_band=1,
        scalar_display_offset=60,
        code_x=code_x,
        queue=True,
        fast_cell_ram=True,
        cell_belts=belt_count,
        packed_cell=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--belts", type=int, default=9)
    parser.add_argument("--code-x", type=int, default=60)
    parser.add_argument("--scalar-belts", type=int, default=1)
    args = parser.parse_args()
    program = build(args.belts, args.code_x, args.scalar_belts)
    output = os.path.join(
        HERE,
        f"reverse-bfs-fifo-b{args.belts}-s{args.scalar_belts}-x{args.code_x}.man",
    )
    program.save(output)
    print("saved", output, "footprint", program.footprint())
