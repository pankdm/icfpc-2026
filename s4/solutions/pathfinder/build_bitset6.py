#!/usr/bin/env python3
"""Pathfinder bitset BFS v6 = v5 + a one-compare walk-back predicate.

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
TARGET = DIST      # v6 stores EPOCH<<8|(dist-1) where v5 stored dist-1
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

    def issue_load(self, addr):
        """Send a read command for scalar[addr] without collecting the reply.

        Digits only (addr < 10), so B is preserved; A ends as addr.
        """
        assert addr < 10
        return self.const(0).e("sc").const(addr).e("sc")

    def mask_update(self, prefetch=None):
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
        # loadv split into issue/collect so an independent read can be
        # pipelined behind the word read (replies return in issue order).
        self.e("M").const(0).e("sc", "W", "sc")    # issue word read
        if prefetch is not None:
            self.issue_load(prefetch)
        self.e("rr")                               # collect word
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


def emit_probe(f, prefix, delta, next_label, prefetched=True, prefetch=True):
    """One BFS probe.  With ``prefetched`` the CUR' reply is already in the
    rr pipe (issued by the predecessor while its word read was in service),
    so the entry read is a bare ``rr``.  With ``prefetch`` every exit toward
    ``next_label`` issues the successor's CUR' read.  The LEFT probe runs
    unprefetched on exit because BFS_POP must stay reply-clean (it is also
    entered from BFS_INIT and POP_STALE)."""
    test = f"{prefix}_TEST"
    enq = f"{prefix}_ENQ"
    go = f"{prefix}_GO"
    done = "ENQ_WD"  # shared: entry B=n survives the branch in every caller

    f.at(test)
    f.e("rr") if prefetched else f.load(CURP)      # read 1 (0-stall if piped)
    delta_ops(f, delta)                            # A=NEI'
    f.e("M").lit(WORD_BITS).e("W", "/")            # A=addr B=sh
    f.e("W", "sp", "W")                            # [sh]; A=addr
    f.e("M").const(0).e("sc", "W", "sc")           # issue word read
    if prefetch:
        f.issue_load(CURP)                         # pipeline successor CUR'
    f.e("rr")                                      # read 2: A=word
    f.e("M", "rp", "W", "}")                       # A=word>>sh
    f.e("M").const(1).e("&")
    f.br(next_label, enq, next_label)

    f.at(enq)
    # Entry: the TEST above always leaves one pending CUR' reply when it
    # prefetches (both branch targets consume exactly one).
    f.e("rr") if prefetch else f.load(CURP)        # read 1
    delta_ops(f, delta)                            # A=NEI'
    f.mask_update(prefetch=CURP if prefetch else None)   # read 2 (+sends)
    f.e("rr") if prefetch else f.load(CURP)        # read 3 (piped)
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
    if prefetch:
        f.issue_load(CURP)                         # pipeline successor CUR'
    f.go(next_label)

    return test


def emit_walk(f, prefix, delta, next_label):
    """Walk candidate, ONE compare: ``cell[NEI] == TARGET``.

    v5 spent a three-stage predicate chain per candidate -- rec>0, then
    rec>>8 == EPOCH, then rec&255 == DIST -- costing four scalar reads and
    three blocks.  But ``rec = epoch<<8 | dist`` is injective in (epoch, dist),
    so the whole chain is a single equality against

        TARGET = EPOCH<<8 | DIST = cell[ROBOT] - 1

    which WALK already has in hand from the record it must read anyway.  rec=0
    (wall / unvisited) and any stale epoch both differ from TARGET, so the
    zero test disappears with the rest.  Tie-breaking is unchanged: the
    candidates are still tried UP, RIGHT, DOWN, LEFT and the first match moves.

    Cost per candidate: 2 scalar reads (CUR, TARGET) + 1 cell read, against
    v5's 4 scalar reads + 1 cell read, and one block instead of three.
    """
    test = f"{prefix}_TEST"
    f.at(test)
    f.e("rp", "sp")                                # A=CUR, re-parked
    delta_ops(f, delta)                            # A=NEI (true idx)
    f.store(NEI)                                   # sends; A=NEI
    f.cell_loadv()                                 # cell read: A=rec
    f.e("M")                                       # B=rec
    f.e("rp", "sp")                                # A=TARGET, re-parked
    f.e("W", "-")                                  # A=rec-TARGET
    f.br(next_label, "MOVE", next_label)
    return test


def build_flow():
    f = Flow()
    f.at("START").const(0).store(EPOCH).const(0).store(I).go("SETUP_LOOP")

    # Setup: one read per cell (load I), one more per wall (loadv).  The
    # scratch copy of I must be drained before mask_update, which juggles
    # its own temporaries through the FIFO.
    # v5 round-tripped the counter through the scalar RAM every cell.  Only the
    # WALL arm needs to: mask_update's scratch traffic is a strict push/pop
    # nest, so a resident value under it would be popped by ITS `rp` (the FIFO
    # is not a stack).  The PATH arm touches no scratch, so ~70% of the 256
    # cells now carry I in the FIFO and skip both the load and the store.
    f.at("SETUP_RELOAD").load(I).e("M").const(1).e("+").go("SETUP_LOOP")
    f.at("SETUP_LOOP").e("sp", "sp")                   # A=I; [I, I]
    f.const(256).e("M", "rp", "-")                     # A=I-256; [I]
    f.br("SETUP_EXIT", "SETUP_EXIT", "SETUP_CELL")
    f.at("SETUP_CELL").inp().br("SETUP_WALL", "SETUP_PATH", "SETUP_WALL")
    f.at("SETUP_WALL").e("rp")                         # A=I; []
    f.store(I)                                         # sends; A=I
    f.e("sp")                                          # [I]
    f.const(OFF_WALL).e("M", "rp", "+")                # A=I+594; []
    f.mask_update()
    f.const(7).e("sd").go("SETUP_RELOAD")
    f.at("SETUP_PATH").const(0).e("sd")                # draw path; [I]
    f.e("rp").e("M").const(1).e("+").go("SETUP_LOOP")  # A=I+1, no RAM
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
    f.issue_load(CURP)          # RAM serves in order: fresh value, piped
    f.go("BFS_UP_TEST")

    # Shared robot-found tail: writes the record (walk reads it) and stops.
    f.at("ENQ_WD").load(REC).cell_storev().go("BFS_DONE")

    emit_probe(f, "BFS_UP", -16, "BFS_RIGHT_TEST")
    emit_probe(f, "BFS_RIGHT", 1, "BFS_DOWN_TEST")
    emit_probe(f, "BFS_DOWN", 16, "BFS_LEFT_TEST")
    emit_probe(f, "BFS_LEFT", -1, "BFS_POP", prefetch=False)

    # Walk-back.  TARGET = cell[ROBOT] - 1 is the whole per-step state: the
    # record is epoch<<8|dist, so subtracting one both keeps the epoch tag and
    # asks for dist-1.  v5 read the robot's record TWICE (once for the epoch
    # tag, once for the distance, because computing hi<<8 clobbered A) and then
    # re-derived EPOCH and DIST inside every candidate.
    f.at("BFS_DONE").go("WALK")
    # CUR lives in the scratch FIFO, not the scalar RAM: each candidate needs
    # it and a scratch echo costs ~15 ticks against a ~154-tick scalar read.
    # Every candidate pops and immediately re-parks it; MOVE drains it.
    f.at("WALK").load(ROBOT)                       # read 1
    f.e("sp")                                      # [CUR]
    f.cell_loadv()                                 # cell read: A=rec(robot)
    f.e("M").const(1).e("W", "-")                  # A=rec-1=TARGET
    f.e("sp")                                      # [CUR, TARGET]
    f.go("WALK_UP_TEST")
    emit_walk(f, "WALK_UP", -16, "WALK_RIGHT_TEST")
    emit_walk(f, "WALK_RIGHT", 1, "WALK_DOWN_TEST")
    emit_walk(f, "WALK_DOWN", 16, "WALK_LEFT_TEST")
    emit_walk(f, "WALK_LEFT", -1, "NO_PATH")

    # The walk left [CUR, TARGET] in the scratch, and CUR *is* the old robot
    # index, so erasing the old cell needs no read at all.  `store` leaves A
    # untouched, so drawing the new one needs none either.  v5 spent four
    # scalar reads here (ROBOT, NEI, FLAG, ROBOT); this spends two.
    f.at("MOVE").e("rp")                           # A=CUR = old robot
    f.e("sa").const(0).e("sd")                     # erase it
    f.e("rp")                                      # drop TARGET
    f.load(NEI).store(ROBOT)                       # read 1; A=NEI
    f.e("sp")                                      # park the new robot index
    f.e("sa").const(10).e("sd")                    # draw it
    f.commit()
    f.e("rp")                                      # A=NEI
    f.e("M").load(FLAG).e("W", "-")                # read 2; A=NEI-FLAG
    f.br("WALK", "ROUND", "WALK")
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
        queue_rows=1,
        queue_right_off=300,
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
        f"reverse-bfs-bitset5-b{args.belts}-s{args.scalar_belts}"
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
