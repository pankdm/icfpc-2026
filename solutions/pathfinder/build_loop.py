#!/usr/bin/env python3
"""Pathfinder with compact indexed U/R/D/L hot loops."""

import argparse
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow
from build_fifo import Flow


I, ROBOT, FLAG, EPOCH, CUR, REC, DIST, NEI = range(8)
TMP, TMP2, X, Y, QVAL, Q_EPOCH, DIRECTION, DELTA = range(8, 16)
SCALAR_RAM_N = 32
RAM_N = 288
CELL0 = 32
BANKED = True
PACKED_CELL = True


def emit_direction_dispatch(f, prefix, target):
    f.at(f"{prefix}_DISPATCH").load(DIRECTION).br(
        f"{prefix}_POS", f"{prefix}_UP", f"{prefix}_UP"
    )
    f.at(f"{prefix}_POS").subc(DIRECTION, 1).br(
        f"{prefix}_GT1", f"{prefix}_RIGHT", f"{prefix}_RIGHT"
    )
    f.at(f"{prefix}_GT1").subc(DIRECTION, 2).br(
        f"{prefix}_LEFT", f"{prefix}_DOWN", f"{prefix}_DOWN"
    )
    f.at(f"{prefix}_UP").const(16).e("N").store(DELTA).go(target)
    f.at(f"{prefix}_RIGHT").const(1).store(DELTA).go(target)
    f.at(f"{prefix}_DOWN").const(16).store(DELTA).go(target)
    f.at(f"{prefix}_LEFT").const(1).e("N").store(DELTA).go(target)


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
    f.display_const(FLAG, 9).addc(EPOCH, 1, EPOCH).go("BFS_INIT")
    f.at("BFS_INIT").epoch_base(TMP).addc(TMP, 1, TMP2)
    f.load(TMP2).cell_store(FLAG, TMP)
    f.epoch_base(TMP).bin("+", TMP, FLAG).queue_push().go("BFS_POP")

    f.at("BFS_POP").queue_pop().store(QVAL).high_epoch(QVAL, Q_EPOCH)
    f.bin("-", Q_EPOCH, EPOCH).br("BFS_POP", "BFS_CURRENT", "BFS_POP")
    f.at("BFS_CURRENT").low_byte(QVAL, CUR)
    f.cell_load(CUR).store(REC).low_byte(REC, DIST)
    f.const(0).store(DIRECTION).go("BFS_DISPATCH")

    emit_direction_dispatch(f, "BFS", "BFS_TEST")
    f.at("BFS_TEST").bin("+", CUR, DELTA, NEI)
    f.cell_load(NEI).store(REC).br(
        "BFS_POSITIVE", "BFS_ENQUEUE", "BFS_NEXT"
    )
    f.at("BFS_POSITIVE").high_epoch(REC, TMP2)
    f.bin("-", TMP2, EPOCH).br("BFS_ENQUEUE", "BFS_NEXT", "BFS_ENQUEUE")
    f.at("BFS_ENQUEUE").epoch_base(TMP).addc(DIST, 1, TMP2)
    f.bin("+", TMP, TMP2).cell_store(NEI, TMP)
    f.epoch_base(TMP).bin("+", TMP, NEI).queue_push()
    f.bin("-", NEI, ROBOT).br("BFS_NEXT", "BFS_DONE", "BFS_NEXT")
    f.at("BFS_NEXT").addc(DIRECTION, 1, DIRECTION)
    f.subc(DIRECTION, 4).br("BFS_DISPATCH", "BFS_POP", "BFS_DISPATCH")

    f.at("BFS_DONE").go("WALK")
    f.at("WALK").load(ROBOT).store(CUR)
    f.cell_load(CUR).store(REC).low_byte(REC, TMP2)
    f.subc(TMP2, 1, DIST).const(0).store(DIRECTION).go("WALK_DISPATCH")

    emit_direction_dispatch(f, "WALK", "WALK_TEST")
    f.at("WALK_TEST").bin("+", CUR, DELTA, NEI)
    f.cell_load(NEI).store(REC).br(
        "WALK_CANDIDATE", "WALK_NEXT", "WALK_NEXT"
    )
    f.at("WALK_CANDIDATE").high_epoch(REC, TMP2)
    f.bin("-", TMP2, EPOCH).br("WALK_NEXT", "WALK_COMPARE", "WALK_NEXT")
    f.at("WALK_COMPARE").low_byte(REC, TMP2)
    f.bin("-", TMP2, DIST).br("WALK_NEXT", "MOVE", "WALK_NEXT")
    f.at("WALK_NEXT").addc(DIRECTION, 1, DIRECTION)
    f.subc(DIRECTION, 4).br("WALK_DISPATCH", "NO_PATH", "WALK_DISPATCH")

    f.at("MOVE").display_const(ROBOT, 0)
    f.load(NEI).store(ROBOT)
    f.display_const(ROBOT, 10).commit()
    f.bin("-", ROBOT, FLAG).br("WALK", "ROUND", "WALK")
    f.at("NO_PATH").e("H")
    return f


def build(belt_count=9, code_x=60):
    return stateflow.build_program(
        build_flow(),
        scalar_size=SCALAR_RAM_N,
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
    args = parser.parse_args()
    program = build(args.belts, args.code_x)
    output = os.path.join(
        HERE, f"reverse-bfs-loop-b{args.belts}-x{args.code_x}.man"
    )
    program.save(output)
    print("saved", output, "footprint", program.footprint())
