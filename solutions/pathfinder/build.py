#!/usr/bin/env python3
"""Generate a reverse-BFS Pathfinder solver.

Cell records:
  -1                       wall
   0                       unvisited path
  (distance + 1) << 9 | q  visited path, q = queue-next index + 1 or zero

Quick checks:
  python3 solutions/pathfinder/verify.py
  python3 tools/grade_fast.py pathfinder solutions/pathfinder/reverse-bfs.man \
      --jobs 4 --progress
"""

import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow


I, ROBOT, FLAG, QH, QT, CUR, REC, NEXT = range(8)
DIST, NEI, TMP, TMP2, X, Y, LIST = range(8, 15)
SCALAR_RAM_N = 32
RAM_N = 288
CELL0 = 32
BANKED = True
NEXT_MASK = 511


class Flow(stateflow.Flow):
    def record_distance(self, record_addr, dst):
        return (
            self.load(record_addr).e("M").const(9).e("W", "}")
            .store(dst)
        )

    def record_next(self, record_addr, dst):
        return (
            self.load(record_addr).e("sp")
            .const(NEXT_MASK).e("M", "rp", "&").store(TMP2)
            .subc(TMP2, 1, dst)
        )


def emit_enqueue(f, prefix, delta, next_label):
    """Try to enqueue CUR+delta, then continue at *next_label*."""
    test = f"{prefix}_TEST"
    enqueue = f"{prefix}_ENQUEUE"
    keep_next = f"{prefix}_KEEP_NEXT"
    set_next = f"{prefix}_SET_NEXT"
    linked = f"{prefix}_LINKED"
    f.at(test)
    (f.addc if delta >= 0 else f.subc)(CUR, abs(delta), NEI)
    f.cell_load(NEI).br(next_label, enqueue, next_label)
    f.at(enqueue)
    # neighbor record := (current distance + 1) << 9
    f.addc(DIST, 1).e("M").const(9).e("W", "{").cell_store(NEI, TMP)
    # old queue tail's low bits := neighbor + 1
    f.addc(NEI, 1, TMP2)
    f.cell_load(QT).e("M").load(TMP2).e("+").cell_store(QT, TMP)
    f.load(NEI).store(QT)
    # If CUR was the queue tail, its saved next was -1. The first newly
    # enqueued neighbor is now the next head; track it in a scalar so BFS does
    # not need to reread CUR after processing all four neighbors.
    f.load(NEXT).br(keep_next, keep_next, set_next)
    f.at(set_next).load(NEI).store(NEXT).go(keep_next)
    f.at(keep_next)
    f.bin("-", NEI, ROBOT).br(linked, "BFS_DONE", linked)
    f.at(linked).go(next_label)
    return test


def emit_walk_choice(f, prefix, delta, next_label):
    """Choose CUR+delta if its stored distance is DIST-1."""
    test = f"{prefix}_TEST"
    candidate = f"{prefix}_CANDIDATE"
    choose = f"{prefix}_CHOOSE"
    f.at(test)
    (f.addc if delta >= 0 else f.subc)(CUR, abs(delta), NEI)
    f.cell_load(NEI).br(candidate, next_label, next_label)
    f.at(candidate).store(REC).record_distance(REC, TMP2)
    f.bin("-", TMP2, NEXT).br(next_label, choose, next_label)
    f.at(choose).go("MOVE")
    return test


def build_flow():
    f = Flow()

    # Setup raster: store -1 for walls, 0 for paths, and stream the matching
    # display colors in row-major order.
    f.at("START").const(0).store(I).go("SETUP_TEST")
    f.at("SETUP_TEST").subc(I, 256).br(
        "SETUP_POSITION", "SETUP_POSITION", "SETUP_CELL"
    )
    f.at("SETUP_CELL").inp().br("SETUP_WALL", "SETUP_PATH", "SETUP_WALL")
    f.at("SETUP_WALL").const(1).e("N").cell_store(I, TMP)
    f.const(7).e("sd").go("SETUP_ADV")
    # Cell RAM is already seeded with zero; only walls require a setup write.
    f.at("SETUP_PATH").const(0).e("sd").go("SETUP_ADV")
    f.at("SETUP_ADV").addc(I, 1, I).go("SETUP_TEST")

    f.at("SETUP_POSITION").inp().store(X).inp().store(Y).index(X, Y, ROBOT)
    f.const(256).store(LIST)
    f.display_const(ROBOT, 10).commit().go("ROUND")

    # Stage the flag in the next display buffer; its first visible frame is
    # still after the first robot move, as required.
    f.at("ROUND").inp().store(X).inp().store(Y).index(X, Y, FLAG)
    f.display_const(FLAG, 9)
    # The prior BFS queue's next pointers form a list of exactly the visited
    # path cells. Clear that list instead of scanning all 256 board cells.
    f.go("CLEAR_TEST")
    f.at("CLEAR_TEST").subc(LIST, 256).br(
        "CLEAR_CELL", "BFS_INIT", "CLEAR_CELL"
    )
    f.at("CLEAR_CELL").load(LIST).store(CUR)
    f.cell_load(CUR).store(REC).record_next(REC, NEXT)
    f.const(0).cell_store(CUR, TMP)
    f.load(NEXT).br("CLEAR_NEXT", "CLEAR_NEXT", "CLEAR_DONE")
    f.at("CLEAR_NEXT").load(NEXT).store(LIST).go("CLEAR_TEST")
    f.at("CLEAR_DONE").const(256).store(LIST).go("BFS_INIT")

    # Flag is BFS distance zero, encoded as layer 1. It is also the initial
    # one-element queue.
    f.at("BFS_INIT").const(512).cell_store(FLAG, TMP)
    f.load(FLAG).store(QH).load(FLAG).store(QT).load(FLAG).store(LIST)
    f.go("BFS_POP")

    f.at("BFS_POP").load(QH).store(CUR)
    f.cell_load(CUR).store(REC).record_distance(REC, DIST)
    f.record_next(REC, NEXT)
    f.go("BFS_UP_TEST")

    emit_enqueue(f, "BFS_UP", -16, "BFS_RIGHT_TEST")
    emit_enqueue(f, "BFS_RIGHT", 1, "BFS_DOWN_TEST")
    emit_enqueue(f, "BFS_DOWN", 16, "BFS_LEFT_TEST")
    emit_enqueue(f, "BFS_LEFT", -1, "BFS_ADVANCE")

    f.at("BFS_ADVANCE").load(NEXT).store(QH).go("BFS_POP")

    # Walk from the robot toward decreasing reverse-BFS distance. NEXT holds
    # the desired neighbor layer for the current step.
    f.at("BFS_DONE").go("WALK")
    f.at("WALK").load(ROBOT).store(CUR)
    f.cell_load(CUR).store(REC).record_distance(REC, DIST)
    f.subc(DIST, 1, NEXT).go("WALK_UP_TEST")

    emit_walk_choice(f, "WALK_UP", -16, "WALK_RIGHT_TEST")
    emit_walk_choice(f, "WALK_RIGHT", 1, "WALK_DOWN_TEST")
    emit_walk_choice(f, "WALK_DOWN", 16, "WALK_LEFT_TEST")
    emit_walk_choice(f, "WALK_LEFT", -1, "NO_PATH")

    f.at("MOVE").display_const(ROBOT, 0)
    f.load(NEI).store(ROBOT)
    f.display_const(ROBOT, 10).commit()
    f.bin("-", ROBOT, FLAG).br("WALK", "ROUND", "WALK")

    # Inputs promise reachability. A stop here turns a violated invariant into
    # an obvious physical failure instead of drawing a plausible wrong frame.
    f.at("NO_PATH").e("H")
    return f


def build():
    return stateflow.build_program(build_flow(), scalar_size=SCALAR_RAM_N)


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "reverse-bfs-linked.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
