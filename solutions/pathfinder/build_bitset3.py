#!/usr/bin/env python3
"""Pathfinder bitset BFS v3: literal divisor, fused offsets, minimal reads.

Scalar RAM reads cost ~150-190 ticks each (split-RAM service + queuing) and
dominated bitset2 (rr stall = 55% of all ticks), so v3 is organised around
read count per operation:

- The word divisor is the palindromic literal `33` (33-bit words, 8 of them),
  placed atomically by boustro; literals load A only, so no CDIV slot read
  and no const_ops B-clobber.
- Mask addresses are fused into the index offset: probing index i tests word
  (i+330)//33 = 10+i//33 with shift i%33 (330 = 10*33), so blocked words live
  at slots 10..17 with no base add and no CBASE read.  Setup writes walls the
  same way with offset 594 = 18*33 (wall words at slots 18..25).
- Per pop, POP_CURRENT precomputes REC = epoch<<8|dist+1 and CUR' = CUR+330
  into slots, so a probe test is exactly 2 reads (CUR', mask word) and an
  enqueue 5 (CUR' x2, mask word, REC, ROBOT); the pop itself is 1 (EPOCH).
- Setup keeps its counter flowing through the scratch FIFO around the const
  compare: ~1 read per path cell, 2 per wall cell.

Slots: 0=CUR' (CUR+330), 1=ROBOT, 2=FLAG, 3=EPOCH, 4=CUR, 5=REC, 6=DIST(walk),
7=NEI, 8=TMP/X, 9=TMP2/Y; blocked words 10..17; wall words 18..25.

The walk-back and MOVE blocks are verbatim build_fifo (exact tie-break parity
with the server-proven champion); queue items are rec<<8|idx as in bitset2.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow
import build_fifo

CURP, ROBOT, FLAG, EPOCH, CUR, REC, DIST, NEI = range(8)
TMP, TMP2 = 8, 9
WORD_BITS = 33
BLK_BASE = 10
WALL_BASE = 18
OFF_BLK = BLK_BASE * WORD_BITS    # 330
OFF_WALL = WALL_BASE * WORD_BITS  # 594
SCALAR_RAM_N = 32
RAM_N = 288
CELL0 = 32
BANKED = True
PACKED_CELL = True
BYTE_MASK = 255

I = CURP  # setup counter lives in the CUR' slot (disjoint phases)


class Flow(build_fifo.Flow):
    """build_fifo macros (packed cell protocol, walk helpers) + mask ops."""

    def lit(self, n):
        """Atomic backtick literal; must be palindromic (boustro reverses
        walk direction on alternate rows) and loads A only (B preserved)."""
        digits = str(n)
        assert digits == digits[::-1], f"literal {n} is not palindromic"
        return self.e(f"`{digits}`")

    def mask_update(self):
        """From A = offset index: mask[idx'//33] |= 1 << (idx'%33).

        One stalling read (loadv); the store is send-only.  Uses the scratch
        FIFO for the third temporary; net scratch balance is zero.
        """
        self.e("M").lit(WORD_BITS).e("W", "/")     # A=addr B=sh
        self.e("sp")                               # [addr]
        self.e("W", "M").const(1).e("{")           # A=1<<sh
        self.e("M", "rp")                          # A=addr B=bit
        self.e("W", "sp", "W")                     # [bit]; A=addr B=bit
        self.e("sp")                               # [bit, addr]
        self.loadv()                               # A=old word
        self.e("M", "rp", "|")                     # A=old|bit
        self.e("M", "rp", "W")                     # A=new B=addr
        return self.storev()


def delta_ops(f, delta):
    """From A=index: A=index+delta via digit constants (B-safe)."""
    f.e("M")
    if abs(delta) == 16:
        f.e("8", "W", "-" if delta < 0 else "+", "-" if delta < 0 else "+")
    elif abs(delta) == 1:
        f.e("1", "W", "-" if delta < 0 else "+")
    else:
        raise ValueError(delta)
    return f


def emit_probe(f, prefix, delta, next_label):
    test = f"{prefix}_TEST"
    enq = f"{prefix}_ENQ"
    go = f"{prefix}_GO"
    done = "ENQ_WD"  # shared: entry B=n survives the branch in every caller

    f.at(test)
    f.load(CURP)                                   # read 1
    delta_ops(f, delta)                            # A=NEI'
    f.e("M").lit(WORD_BITS).e("W", "/")            # A=addr B=sh
    f.e("W", "sp", "W")                            # [sh]; A=addr
    f.loadv()                                      # read 2: A=word
    f.e("M", "rp", "W", "}")                       # A=word>>sh
    f.e("M").const(1).e("&")
    f.br(next_label, enq, next_label)

    f.at(enq)
    f.load(CURP)                                   # read 1
    delta_ops(f, delta)                            # A=NEI'
    f.mask_update()                                # read 2 (+sends)
    f.load(CURP)                                   # read 3
    delta_ops(f, delta)                            # A=NEI'
    f.e("sp").const(OFF_BLK).e("M", "rp", "-")     # A=n (true index)
    f.store(NEI)                                   # sends; A=n
    # Robot check first: B=n survives the branch, and both arms still write
    # the cell record (the walk reads it); only the doomed queue push and
    # visited-set bookkeeping differ, which the next epoch drains anyway.
    f.e("M").load(ROBOT).e("-")                    # read 4; A=R-n, B=n
    f.br(go, done, go)

    # Record + queue item, keeping n/rec in registers and scratch.
    f.at(go).load(REC)                             # read 5; A=rec B=n
    f.e("W", "sp", "W", "sp")                      # [n, rec]; A=rec B=n
    f.e("M").const(8).e("W", "{")                  # A=rec<<8
    f.e("M", "rp", "+").queue_push()               # A=rec<<8+n; [rec]
    f.e("rp", "M")                                 # A=rec... B=rec
    f.load(NEI).e("W")                             # read 6; A=rec B=n
    f.cell_storev()                                # sends
    f.go(next_label)

    return test


def build_flow():
    f = Flow()
    f.at("START").const(0).store(EPOCH).const(0).store(I).go("SETUP_LOOP")

    # Setup: one read per cell (load I), one more per wall (loadv).  The
    # scratch copy of I must be drained before mask_update, which juggles
    # its own temporaries through the FIFO.
    f.at("SETUP_LOOP").load(I).e("sp", "sp")           # read; [I, I]
    f.e("M").const(1).e("+").store(I)                  # I := I+1 (sends)
    f.const(256).e("M", "rp", "-")                     # A=I-256; [I]
    f.br("SETUP_EXIT", "SETUP_EXIT", "SETUP_CELL")
    f.at("SETUP_CELL").inp().br("SETUP_WALL", "SETUP_PATH", "SETUP_WALL")
    f.at("SETUP_WALL").const(OFF_WALL).e("M", "rp", "+")   # A=I+594; []
    f.mask_update()
    f.const(7).e("sd").go("SETUP_LOOP")
    f.at("SETUP_PATH").e("rp")                         # drop I; []
    f.const(0).e("sd").go("SETUP_LOOP")
    f.at("SETUP_EXIT").e("rp")                         # drain [I]
    f.inp().store(TMP).inp().store(TMP2)
    f.index(TMP, TMP2, ROBOT)
    f.display_const(ROBOT, 10).commit().go("ROUND")

    f.at("ROUND").inp().store(TMP).inp().store(TMP2).index(TMP, TMP2, FLAG)
    f.display_const(FLAG, 9)
    f.addc(EPOCH, 1, EPOCH)
    for i in range(8):
        f.load(WALL_BASE + i).store(BLK_BASE + i)
    f.go("BFS_INIT")

    f.at("BFS_INIT")
    f.const(OFF_BLK).e("M").load(FLAG).e("+")      # A=FLAG'
    f.mask_update()
    f.load(EPOCH).e("M").const(8).e("W", "{")      # A=E8
    f.e("M").const(1).e("+")                       # A=rec=E8+1
    f.e("sp").load(FLAG).e("M", "rp").cell_storev()
    f.e("M").const(8).e("W", "{", "M").load(FLAG).e("+").queue_push()
    f.go("BFS_POP")

    # Pop: 1 read (EPOCH).  REC := h+1 and CUR' := CUR+330 are precomputed
    # for the four probes; DIST is not stored (the walk derives its own).
    f.at("BFS_POP").queue_pop().e("sp").const(16).e("M", "rp", "sp", "}")
    f.e("M").load(EPOCH).e("-").br("POP_STALE", "POP_CURRENT", "POP_STALE")
    f.at("POP_STALE").e("rp").go("BFS_POP")
    f.at("POP_CURRENT").e("rp", "sp", "M").const(8).e("W", "}")  # A=h; [q]
    f.e("M").const(1).e("+").store(REC)            # REC=h+1; A=rec B=addr
    f.e("M").const(1).e("W", "-")                  # A=rec-1=h
    f.e("M").const(8).e("W", "{")                  # A=h<<8
    f.e("M", "rp", "-").store(CUR)                 # CUR=q-h<<8; A=CUR
    f.e("sp").const(OFF_BLK).e("M", "rp", "+").store(CURP)
    f.go("BFS_UP_TEST")

    # Shared robot-found tail: writes the record (walk reads it) and stops.
    f.at("ENQ_WD").load(REC).cell_storev().go("BFS_DONE")

    emit_probe(f, "BFS_UP", -16, "BFS_RIGHT_TEST")
    emit_probe(f, "BFS_RIGHT", 1, "BFS_DOWN_TEST")
    emit_probe(f, "BFS_DOWN", 16, "BFS_LEFT_TEST")
    emit_probe(f, "BFS_LEFT", -1, "BFS_POP")

    # Walk-back: verbatim build_fifo semantics (exact tie-breaking parity).
    f.at("BFS_DONE").go("WALK")
    f.at("WALK").load(ROBOT).store(CUR)
    f.cell_load(CUR).store(REC).low_byte(REC, TMP2)
    f.subc(TMP2, 1, DIST).go("WALK_UP_TEST")
    build_fifo.emit_walk_choice(f, "WALK_UP", -16, "WALK_RIGHT_TEST")
    build_fifo.emit_walk_choice(f, "WALK_RIGHT", 1, "WALK_DOWN_TEST")
    build_fifo.emit_walk_choice(f, "WALK_DOWN", 16, "WALK_LEFT_TEST")
    build_fifo.emit_walk_choice(f, "WALK_LEFT", -1, "NO_PATH")

    f.at("MOVE").display_const(ROBOT, 0)
    f.load(NEI).store(ROBOT)
    f.display_const(ROBOT, 10).commit()
    f.bin("-", ROBOT, FLAG).br("WALK", "ROUND", "WALK")
    f.at("NO_PATH").e("H")
    return f


def build_reflow(belts=9, scalar_belts=4, code_x=0, op_slack=0, verify=True):
    import boustro
    from build_reflow_banked import alias_empty_gotos

    flow = alias_empty_gotos(build_flow())
    layout = {}

    def lay(program, graph, port_spec, code_x=code_x):
        # Columns occupied by component literals (split-RAM init backticks)
        # below the controller: a controller backtick sharing such a column
        # would form a bogus vertical literal in the wasm loader.
        forbid = set(range(code_x + 40, code_x + 70))
        forbid |= set(range(code_x + 156, code_x + 184))
        result = boustro.lay_cfg_boustrophedon(
            program, graph, port_spec, code_x=code_x, op_slack=op_slack,
            lit_forbid=forbid,
        )
        layout.update(result)
        return result

    program = stateflow.build_program(
        flow,
        scalar_size=SCALAR_RAM_N,
        scalar_belts=scalar_belts,
        fast_scalar_ram=True,
        scalar_command_band=2,
        scalar_reply_band=1,
        scalar_display_offset=60,
        code_x=code_x,
        queue=True,
        fast_cell_ram=True,
        cell_belts=belts,
        packed_cell=True,
        lay_fn=lay,
    )
    if verify:
        import boustro as b
        b.verify_bindings(program, layout)
    return program, layout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--belts", type=int, default=9)
    parser.add_argument("--scalar-belts", type=int, default=4)
    parser.add_argument("--code-x", type=int, default=0)
    parser.add_argument("--op-slack", type=int, default=0)
    parser.add_argument("--out")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    output = args.out or os.path.join(
        HERE,
        f"reverse-bfs-bitset3-b{args.belts}-s{args.scalar_belts}"
        f"-reflow-cx{args.code_x}-o{args.op_slack}.man",
    )
    program, layout = build_reflow(
        args.belts, args.scalar_belts, args.code_x, args.op_slack,
        verify=not args.no_verify,
    )
    program.save(output)
    print(
        "saved", output,
        "footprint", program.footprint(),
        "controller", layout["width"], "x", layout["height"],
        "corridors", layout["ncorr"],
    )
