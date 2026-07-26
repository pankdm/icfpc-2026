#!/usr/bin/env python3
"""Generate the linked-cell Snake solver.

Quick checks:
  python3 solutions/snake/verify.py
  python3 tools/grade_fast.py snake solutions/snake/linked.man --jobs 4 --progress
"""

import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow


# Scalar state. Cell RAM stores a linked body: each occupied cell contains the
# next body's index + 1; the head contains HEAD_SENTINEL.
X, Y, HEAD, TAIL, DIR, FRUIT, CMD, NEW = range(8)
TMP, TMP2, NEXT, GROW, COLOR, I = range(8, 14)
HEAD_SENTINEL = 257
NO_FRUIT = 256
SCALAR_RAM_N = 32
RAM_N = 288  # flattened scalar+cell size used by the semantic verifier
CELL0 = 32  # semantic verifier's logical combined-RAM offset
BANKED = True


class Flow(stateflow.Flow):
    pass


def build_flow():
    f = Flow()

    # Setup: one-cell snake moving right.
    f.at("START").inp().store(X).inp().store(Y)
    f.index(X, Y, HEAD).load(HEAD).store(TAIL)
    f.const(3).store(DIR)
    f.const(NO_FRUIT).store(FRUIT)
    f.const(HEAD_SENTINEL).cell_store(HEAD, TMP)
    f.display_const(HEAD, 10).commit().go("ROUND")

    # A zero-frame direction round is consumed immediately. Input gating in the
    # judge releases the following round as soon as this round's sole value is read.
    f.at("ROUND").inp().store(CMD)
    f.load(CMD).br("COMMAND", "TICK", "COMMAND")
    f.at("COMMAND").subc(CMD, 1).br("DIRECTION", "FRUIT_SPAWN", "DIRECTION")
    f.at("FRUIT_SPAWN").inp().store(X).inp().store(Y).index(X, Y, FRUIT)
    f.display_const(FRUIT, 9).commit().go("ROUND")
    f.at("DIRECTION").load(CMD).store(DIR).go("ROUND")

    # Compute the candidate head with explicit boundary checks.
    f.at("TICK").load(HEAD).store(NEW)
    f.subc(DIR, 2).br("DIR_NOT_UP", "MOVE_UP", "DIR_NOT_UP")
    f.at("DIR_NOT_UP").subc(DIR, 3).br("DIR_4PLUS", "MOVE_RIGHT", "DIR_4PLUS")
    f.at("DIR_4PLUS").subc(DIR, 4).br("MOVE_LEFT", "MOVE_DOWN", "MOVE_LEFT")

    f.at("MOVE_UP").load(HEAD).e("M").const(4).e("W", "}").br(
        "UP_OK", "LOSE", "UP_OK"
    )
    f.at("UP_OK").subc(HEAD, 16, NEW).go("CHECK_FRUIT")

    f.at("MOVE_DOWN").load(HEAD).e("M").const(4).e("W", "}").store(TMP)
    # y - 15: negative means inside, zero means bottom edge.
    f.subc(TMP, 15).br("LOSE", "LOSE", "DOWN_OK")
    f.at("DOWN_OK").addc(HEAD, 16, NEW).go("CHECK_FRUIT")

    f.at("MOVE_RIGHT").load(HEAD).e("sp").const(15).e("M", "rp", "&").store(TMP)
    f.subc(TMP, 15).br("RIGHT_OK", "LOSE", "RIGHT_OK")
    f.at("RIGHT_OK").addc(HEAD, 1, NEW).go("CHECK_FRUIT")

    f.at("MOVE_LEFT").load(HEAD).e("sp").const(15).e("M", "rp", "&").br(
        "LEFT_OK", "LOSE", "LEFT_OK"
    )
    f.at("LEFT_OK").subc(HEAD, 1, NEW).go("CHECK_FRUIT")

    # GROW is boolean. An occupied NEW is legal only for a non-growing move
    # into the current tail, because that tail is vacated before the head lands.
    f.at("CHECK_FRUIT").bin("-", NEW, FRUIT).br(
        "NOT_GROW", "IS_GROW", "NOT_GROW"
    )
    f.at("IS_GROW").const(1).store(GROW).go("CHECK_OCCUPIED")
    f.at("NOT_GROW").const(0).store(GROW).go("CHECK_OCCUPIED")
    f.at("CHECK_OCCUPIED").cell_load(NEW).br(
        "OCCUPIED", "APPLY_MOVE", "OCCUPIED"
    )
    f.at("OCCUPIED").load(GROW).br("LOSE", "OCC_TAIL_TEST", "LOSE")
    f.at("OCC_TAIL_TEST").bin("-", NEW, TAIL).br(
        "LOSE", "APPLY_MOVE", "LOSE"
    )

    # Length-one movement needs no link update on the old head. Longer
    # non-growth movement first pops the linked tail.
    f.at("APPLY_MOVE").load(GROW).br("APPEND", "NON_GROW", "APPEND")
    f.at("NON_GROW").bin("-", HEAD, TAIL).br(
        "POP_TAIL", "MOVE_LENGTH_ONE", "POP_TAIL"
    )
    f.at("MOVE_LENGTH_ONE").display_const(TAIL, 0)
    f.const(0).cell_store(TAIL, TMP)
    f.load(NEW).store(HEAD).load(NEW).store(TAIL)
    f.const(HEAD_SENTINEL).cell_store(HEAD, TMP)
    f.display_const(TAIL, 10).go("COMMIT_TICK")

    f.at("POP_TAIL").cell_load(TAIL).store(TMP2)
    f.subc(TMP2, 1, NEXT)
    f.display_const(TAIL, 0)
    f.const(0).cell_store(TAIL, TMP)
    f.load(NEXT).store(TAIL).go("APPEND")

    f.at("APPEND")
    # old head's next pointer := NEW+1; NEW becomes the sentinel head.
    f.addc(NEW, 1, TMP2)
    f.load(TMP2).cell_store(HEAD, TMP)
    f.load(NEW).store(HEAD)
    f.const(HEAD_SENTINEL).cell_store(HEAD, TMP)
    f.display_const(HEAD, 10)
    f.load(GROW).br("CLEAR_FRUIT", "COMMIT_TICK", "CLEAR_FRUIT")
    f.at("CLEAR_FRUIT").const(NO_FRUIT).store(FRUIT).go("COMMIT_TICK")
    f.at("COMMIT_TICK").commit().go("ROUND")

    # Collision leaves the snake in place and recolors every occupied cell red.
    # The body is a linked list (cell = next+1, head = HEAD_SENTINEL), so walk
    # TAIL->HEAD in length-L steps instead of scanning all 256 cells: the red
    # recoloring is the final output, so its cost lands in every settle time.
    f.at("LOSE").load(TAIL).store(I).go("LOSE_STEP")
    f.at("LOSE_STEP").display_const(I, 9)
    f.cell_load(I).store(TMP)
    f.subc(TMP, HEAD_SENTINEL).br("LOSE_NEXT", "LOSE_COMMIT", "LOSE_NEXT")
    f.at("LOSE_NEXT").subc(TMP, 1, I).go("LOSE_STEP")
    f.at("LOSE_COMMIT").commit().go("ROUND")
    return f


def build(**kwargs):
    kwargs.setdefault("scalar_size", SCALAR_RAM_N)
    return stateflow.build_program(build_flow(), **kwargs)


VARIANTS = {
    # The default code_x=380 spends 320 blank columns on edge lanes the CFG
    # never needed; 60 is the smallest that still fits the pooled lanes.
    "linked.man": {},
    "linked-cx60-fast8.man": dict(code_x=60, fast_cell_ram=True, cell_belts=8),
    # scalar_belts=8 fails all cases; 4 belts (8 values each) is the working config.
    "linked-cx60-fast8-fs4.man": dict(
        code_x=60, fast_cell_ram=True, cell_belts=8,
        fast_scalar_ram=True, scalar_belts=4,
    ),
    # COMPACT_PORTS floor: walks 250->155 cols, display feeds drop straight in.
    # cell_belts=4 hangs (no verdict on every case); 8 belts is the config.
    "linked-compact-cx60-cb8.man": dict(
        code_x=60, compact=True, fast_cell_ram=True, cell_belts=8,
        fast_scalar_ram=True, scalar_belts=4,
    ),
    # Only 14 scalar addresses are used: a 16-slot scalar (4 cells/belt)
    # halves the hottest RAM latency. cell_belts=16 fails all cases.
    "linked-compact-s16-cx45.man": dict(
        scalar_size=16, code_x=45, compact=True, fast_cell_ram=True,
        cell_belts=8, fast_scalar_ram=True, scalar_belts=4,
    ),
    # Boustrophedon controller: wrap shims become op rows, 347->313 tall.
    "linked-bstr.man": dict(
        scalar_size=16, code_x=45, compact=True, fast_cell_ram=True,
        cell_belts=8, fast_scalar_ram=True, scalar_belts=4, boustrophedon=True,
    ),
    # Same config under the smtrows-searched COMPACT_PORTS (154->143 op rows).
    "linked-smtports.man": dict(
        scalar_size=16, code_x=45, compact=True, fast_cell_ram=True,
        cell_belts=8, fast_scalar_ram=True, scalar_belts=4, boustrophedon=True,
    ),
}


if __name__ == "__main__":
    for name, kwargs in VARIANTS.items():
        program = build(**kwargs)
        output = os.path.join(HERE, name)
        program.save(output)
        print("saved", output, "footprint", program.footprint())
