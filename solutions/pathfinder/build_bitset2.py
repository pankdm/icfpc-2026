#!/usr/bin/env python3
"""Pathfinder with register-juggled 256-bit occupancy masks in scalar RAM.

The BFS expansion never reads cell RAM: a probe tests one bit of a fused
blocked mask (wall|visited, four 64-bit scalar words) using the divide op to
produce word index and shift amount in a single instruction, with the scratch
FIFO as the third register.  Distances ride the queue items, so pops skip the
cell read as well.  Cell records (epoch<<8|dist) are write-only during BFS and
serve only the walk-back, which is kept verbatim from build_fifo so the
tie-breaking path is bit-identical to the server-proven FIFO champion.

Slot map: 0=I/E8 (setup counter, then EPOCH<<8), 1=ROBOT, 2=FLAG, 3=EPOCH,
4=CUR, 5=REC, 6=DIST, 7=NEI, 8=TMP/X/CDIV, 9=TMP2/Y/CBASE (all <10 so loads
preserve B), 16..23 blocked words, 24..31 wall words (cold).

const_ops(n>=10) clobbers B (its doubling chain uses M), so the divisor and
the mask base live in scalar slots: slot 8 holds 32, slot 9 holds the mask base
(WALL_BASE during setup, BLK_BASE from each ROUND on).  Both slots are
reused as X/Y scratch by the round parser and slot 9 as TMP2 by the walk;
neither overlaps the BFS window where the constants are live.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow
import build_fifo

I, ROBOT, FLAG, EPOCH, CUR, REC, DIST, NEI = range(8)
TMP, TMP2 = 8, 9
E8 = 0          # reuses the setup counter slot; live from ROUND onward
CDIV = 8        # constant 32 (word split divisor), live in setup walls + BFS
CBASE = 9       # mask base constant: WALL_BASE during setup, BLK_BASE in BFS
WORD_BITS = 32  # 32-bit words: split scalar RAM belts multiply stored values
                # by 9^k while routing and sign-route with X, so stored values
                # must stay positive and comfortably below 2^63/9^9
BLK_BASE = 16   # blocked = wall | visited-this-epoch, 8 words, reset per round
WALL_BASE = 24  # pristine wall words, written once at setup
SCALAR_RAM_N = 32
RAM_N = 288
CELL0 = 32
BANKED = True
PACKED_CELL = True
BYTE_MASK = 255


class Flow(build_fifo.Flow):
    """build_fifo macros (packed cell protocol, walk helpers) + mask ops."""

    def word_split(self):
        """A=index -> A=word(index>>5), B=sh(index&31) via one divide.

        Loads the divisor from slot CDIV (addr<10 keeps B) because const_ops
        for values >= 10 clobbers B with its doubling chain.
        """
        return self.e("M").load(CDIV).e("W", "/")

    def bit_set(self, index_addr):
        """mask[CBASE + index>>5] |= 1 << (index&31)."""
        self.load(index_addr).word_split()         # A=word B=sh
        self.e("sp")                               # push word
        self.e("W", "M").const(1).e("{")           # A = 1<<sh
        self.e("M", "rp")                          # A=word B=bit
        self.e("W", "sp", "W")                     # push bit; A=word B=bit
        self.e("M").load(CBASE).e("+")             # A = base+word
        self.e("sp")                               # push addr
        self.loadv()                               # A = old word
        self.e("M", "rp", "|")                     # A = old|bit
        self.e("M", "rp", "W")                     # A=new B=addr
        return self.storev()


def signed_add(f, source, delta, dst=None):
    return (
        f.addc(source, delta, dst) if delta >= 0
        else f.subc(source, -delta, dst)
    )


def emit_probe(f, prefix, delta, next_label):
    """BFS expansion probe: mask test, then write-only enqueue on success."""
    test = f"{prefix}_TEST"
    enq = f"{prefix}_ENQ"
    linked = f"{prefix}_LINKED"
    f.at(test)
    signed_add(f, CUR, delta)                      # A = NEI (unstored)
    f.bit_test_inline(next_label, enq)
    f.at(enq)
    signed_add(f, CUR, delta, NEI)
    f.bit_set(NEI)
    # rec := E8 + DIST + 1; cell[NEI] := rec (write-only, no epoch read).
    f.load(E8).e("M").load(DIST).e("+", "M").const(1).e("+")
    f.e("sp").load(NEI).e("M", "rp").cell_storev()
    # qval := rec<<8 + NEI  (epoch<<16 | dist<<8 | idx).
    f.e("M").const(8).e("W", "{", "M").load(NEI).e("+").queue_push()
    f.bin("-", NEI, ROBOT).br(linked, "BFS_DONE", linked)
    f.at(linked).go(next_label)
    return test


def _bit_test_inline(self, on_set, on_clear):
    """Branch on the blocked bit for the index in A (never stored).

    Two scalar data roundtrips (loadv word + two constant-slot loads) and one
    scratch echo; ends with A in {0,1}, zero -> on_clear.
    """
    self.word_split()                          # A=word B=sh
    self.e("W", "sp", "W")                     # push sh; A=word B=sh
    self.e("M").load(CBASE).e("+")             # A = base+word
    self.loadv()                               # A = mask word
    self.e("M", "rp", "W", "}")                # A = word >> sh
    self.e("M").const(1).e("&")
    return self.br(on_set, on_clear, on_set)


Flow.bit_test_inline = _bit_test_inline


def build_flow():
    f = Flow()
    f.at("START").const(0).store(I).const(0).store(EPOCH)
    f.const(WORD_BITS).store(CDIV).const(WALL_BASE).store(CBASE).go("SETUP_TEST")
    f.at("SETUP_TEST").subc(I, 256).br(
        "SETUP_POSITION", "SETUP_POSITION", "SETUP_CELL"
    )
    f.at("SETUP_CELL").inp().br("SETUP_WALL", "SETUP_PATH", "SETUP_WALL")
    f.at("SETUP_WALL").bit_set(I)
    f.const(7).e("sd").go("SETUP_ADV")
    f.at("SETUP_PATH").const(0).e("sd").go("SETUP_ADV")
    f.at("SETUP_ADV").addc(I, 1, I).go("SETUP_TEST")
    f.at("SETUP_POSITION").inp().store(TMP).inp().store(TMP2)
    f.index(TMP, TMP2, ROBOT)
    f.display_const(ROBOT, 10).commit().go("ROUND")

    f.at("ROUND").inp().store(TMP).inp().store(TMP2).index(TMP, TMP2, FLAG)
    f.display_const(FLAG, 9)
    f.addc(EPOCH, 1, EPOCH)
    f.load(EPOCH).e("M").const(8).e("W", "{").store(E8)
    f.const(WORD_BITS).store(CDIV).const(BLK_BASE).store(CBASE)
    # blocked := wall (visited reset).
    for i in range(8):
        f.load(WALL_BASE + i).store(BLK_BASE + i)
    f.go("BFS_INIT")

    # Seed flag: blocked bit, record E8+1, queue item (E8+1)<<8|FLAG.
    f.at("BFS_INIT").bit_set(FLAG)
    f.load(E8).e("M").const(1).e("+")
    f.e("sp").load(FLAG).e("M", "rp").cell_storev()
    f.e("M").const(8).e("W", "{", "M").load(FLAG).e("+").queue_push()
    f.go("BFS_POP")

    # Pop: drain stale epochs, split qval into CUR and DIST without cell RAM.
    # const(16) clobbers B, so stage qval through scratch around it.
    f.at("BFS_POP").queue_pop().e("sp").const(16).e("M", "rp", "sp", "}")
    f.e("M").load(EPOCH).e("-").br("POP_STALE", "POP_CURRENT", "POP_STALE")
    f.at("POP_STALE").e("rp").go("BFS_POP")
    f.at("POP_CURRENT").e("rp", "sp", "M").const(8).e("W", "}")   # A=h=rec
    f.e("sp", "M").const(8).e("W", "{")                           # A=h<<8
    f.e("M", "rp", "-").store(CUR)                                # CUR=qval-h<<8
    f.e("rp", "M").load(E8).e("W", "-").store(DIST)               # DIST=h-E8
    f.go("BFS_UP_TEST")

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


def build(belt_count=9, code_x=60, scalar_belts=4):
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
    parser.add_argument("--scalar-belts", type=int, default=4)
    args = parser.parse_args()
    program = build(args.belts, args.code_x, args.scalar_belts)
    output = os.path.join(
        HERE,
        f"reverse-bfs-bitset2-b{args.belts}-s{args.scalar_belts}"
        f"-x{args.code_x}.man",
    )
    program.save(output)
    print("saved", output, "footprint", program.footprint())
