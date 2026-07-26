#!/usr/bin/env python3
"""Pathfinder with four batched neighbor reads per BFS expansion."""

import argparse
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow


I, ROBOT, FLAG, EPOCH, CUR, REC, DIST, NEI = range(8)
TMP, TMP2, X, Y, QVAL, Q_EPOCH = range(8, 14)
NU, NR, ND, NL = range(14, 18)
SCALAR_RAM_N = 32
RAM_N = 288
CELL0 = 32
BANKED = True
PACKED_CELL = True
BYTE_MASK = 255


class Flow(stateflow.Flow):
    def __init__(self, replicas=1):
        super().__init__()
        self.replicas = replicas

    def cell_loadv(self):
        return self.e("cc", "cr") if self.replicas == 1 else self.e("c0s", "c0r")

    def cell_storev(self):
        return self.e("sp", "W", "M").const(1).e(
            "W", "+", "N", "cc", "rp", "cc"
        )

    def cell_store(self, index_addr, stage_addr):
        if self.replicas == 1:
            return super().cell_store(index_addr, stage_addr)
        self.store(stage_addr)
        for replica in range(self.replicas):
            self.load(index_addr).e("M").load(stage_addr).e("sp", "W", "M")
            self.const(1).e(
                "W", "+", "N", f"c{replica}s", "rp", f"c{replica}s"
            )
        return self

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

    def queue_record(self, index_addr, distance_addr):
        self.epoch_base16(TMP)
        self.load(distance_addr).e("M").const(8).e("W", "{")
        self.e("M").load(TMP).e("+", "M").load(index_addr).e("+")
        return self.queue_push()

    def cell_read_send(self, index_addr, replica=0):
        token = "cc" if self.replicas == 1 else f"c{replica}s"
        return self.load(index_addr).e(token)


def signed_add(f, source, delta, dst):
    return f.addc(source, delta, dst) if delta >= 0 else f.subc(source, -delta, dst)


def emit_result(f, prefix, nei_addr, next_label, done_label, replica):
    positive = f"{prefix}_POSITIVE"
    enqueue = f"{prefix}_ENQUEUE"
    linked = f"{prefix}_LINKED"
    reply = "cr" if f.replicas == 1 else f"c{replica}r"
    f.at(f"{prefix}_RESULT").e(reply).store(REC).br(
        positive, enqueue, next_label
    )
    f.at(positive).high_epoch8(REC, TMP2)
    f.bin("-", TMP2, EPOCH).br(enqueue, next_label, enqueue)
    f.at(enqueue).addc(DIST, 1, TMP2)
    f.epoch_base8(TMP).bin("+", TMP, TMP2).cell_store(nei_addr, REC)
    f.queue_record(nei_addr, TMP2)
    f.bin("-", nei_addr, ROBOT).br(linked, done_label, linked)
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


def build_flow(replicas=1):
    f = Flow(replicas)
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

    f.at("BFS_INIT").const(1).store(DIST)
    f.epoch_base8(TMP).addc(TMP, 1, TMP2)
    f.load(TMP2).cell_store(FLAG, REC)
    f.queue_record(FLAG, DIST).go("BFS_POP")

    f.at("BFS_POP").queue_pop().store(QVAL).queue_epoch(QVAL, Q_EPOCH)
    f.bin("-", Q_EPOCH, EPOCH).br("BFS_POP", "BFS_CURRENT", "BFS_POP")
    f.at("BFS_CURRENT").low_byte(QVAL, CUR).queue_distance(QVAL, DIST)
    signed_add(f, CUR, -16, NU)
    signed_add(f, CUR, 1, NR)
    signed_add(f, CUR, 16, ND)
    signed_add(f, CUR, -1, NL)
    f.cell_read_send(NU, 0).cell_read_send(NR, 1 if replicas > 1 else 0)
    f.cell_read_send(ND, 2 if replicas > 1 else 0)
    f.cell_read_send(NL, 3 if replicas > 1 else 0).go("BFS_UP_RESULT")

    emit_result(f, "BFS_UP", NU, "BFS_RIGHT_RESULT", "BFS_DRAIN3", 0)
    emit_result(f, "BFS_RIGHT", NR, "BFS_DOWN_RESULT", "BFS_DRAIN2", 1 if replicas > 1 else 0)
    emit_result(f, "BFS_DOWN", ND, "BFS_LEFT_RESULT", "BFS_DRAIN1", 2 if replicas > 1 else 0)
    emit_result(f, "BFS_LEFT", NL, "BFS_POP", "BFS_DONE", 3 if replicas > 1 else 0)

    f.at("BFS_DRAIN3").e("c1r" if replicas > 1 else "cr").go("BFS_DRAIN2")
    f.at("BFS_DRAIN2").e("c2r" if replicas > 1 else "cr").go("BFS_DRAIN1")
    f.at("BFS_DRAIN1").e("c3r" if replicas > 1 else "cr").go("BFS_DONE")
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


def build(belt_count=9, code_x=60, replicas=1):
    return stateflow.build_program(
        build_flow(replicas),
        scalar_size=SCALAR_RAM_N,
        code_x=code_x,
        queue=True,
        fast_cell_ram=True,
        cell_belts=belt_count,
        packed_cell=True,
        cell_replicas=replicas,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--belts", type=int, default=9)
    parser.add_argument("--code-x", type=int, default=60)
    parser.add_argument("--replicas", type=int, choices=(1, 4), default=1)
    args = parser.parse_args()
    program = build(args.belts, args.code_x, args.replicas)
    output = os.path.join(
        HERE,
        f"reverse-bfs-async-r{args.replicas}-b{args.belts}-x{args.code_x}.man",
    )
    program.save(output)
    print("saved", output, "footprint", program.footprint())
