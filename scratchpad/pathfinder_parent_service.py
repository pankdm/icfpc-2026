#!/usr/bin/env python3
"""Resettable/queryable canonical 64-word Pathfinder parent ring.

The service accepts a single tagged command stream:

    [1, t0, ..., t63]     update one complete BFS layer and echo 1
    [-1, m0, ..., m63]    query all words and emit [-1, hit0, ..., hit63]
    [0]                   replace all sixty-four words with zero and echo 0

The update batch is in row-major U/R/L/D order.  Query
masks are normally zero except at the robot row's four directions.  This is an
intentionally
unrolled correctness probe; once the protocol is integrated, BP loops can
fold the two sixteen-operation control blocks.
"""

import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import flowgrid
import littleman as lm
import boustro


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-parent-service.man"
SLOTS = 64


def build_flow():
    flow = flowgrid.Flow()
    flow.at("COMMAND").e("ci").br("UPDATE", "RESET", "QUERY")

    flow.at("UPDATE").e("8", "M", "*", "b").go("UPDATE_LOOP")
    flow.at("UPDATE_LOOP").e("ci", "M", "rr", "|", "rs", "m")
    flow.e(("brbp", "UPDATE_LOOP", "UPDATE_DONE"))
    flow.at("UPDATE_DONE").const(1).e("co").go("COMMAND")

    flow.at("QUERY").e("co", "8", "M", "*", "b").go("QUERY_LOOP")
    # Return the parent before masking it.  B retains the selector mask.
    flow.at("QUERY_LOOP").e("ci", "M", "rr", "rs", "&", "co", "m")
    flow.e(("brbp", "QUERY_LOOP", "COMMAND"))

    flow.at("RESET").e("co", "8", "M", "*", "b").go("RESET_LOOP")
    flow.at("RESET_LOOP").e("rr", "0", "rs", "m")
    flow.e(("brbp", "RESET_LOOP", "COMMAND"))
    return flow


def add_service(program, x0=0, y0=0, with_io=False):
    columns = {
        "ci": (-45, "r"),
        "co": (-30, "s"),
        "rr": (-15, "r"),
        "rs": (0, "s"),
    }
    layout = boustro.lay_cfg_boustrophedon(
        program,
        build_flow(),
        columns,
        code_x=55,
        x0=x0,
        y0=y0,
        op_slack=8,
    )
    ports = layout["ports"]
    bottom = layout["bottom"]

    if with_io:
        program.input_room(ports["ci"][0] - 1, bottom + 8)
        program.pipe([(ports["ci"][0], bottom + 7), ports["ci"]])
        program.output_room(ports["co"][0] - 1, bottom + 8)
        program.pipe([ports["co"], (ports["co"][0], bottom + 7)])

    # Seed sixty-four zeroes, then turn the same man into the permanent relay.
    # This avoids a phase-handoff pipe whose endpoint can otherwise bind to
    # the relay's nearby send rather than its receive.
    relay_x, relay_y = x0 + 60, bottom + 12
    program.room(relay_x, relay_y, 15, 7)
    program.text(relay_x + 1, relay_y + 1, ">@8M*b0>smd")
    program.put(relay_x + 11, relay_y + 2, "<")
    program.put(relay_x + 8, relay_y + 2, "^")
    program.put(relay_x + 12, relay_y + 1, "v")
    program.put(relay_x + 12, relay_y + 3, "<")
    program.put(relay_x + 4, relay_y + 3, "v")
    program.text(relay_x + 4, relay_y + 4, ">Rsv")
    program.put(relay_x + 7, relay_y + 5, "<")
    program.put(relay_x + 4, relay_y + 5, "^")

    program.pipe([
        ports["rs"],
        (ports["rs"][0], bottom + 3),
        (relay_x + 25, bottom + 3),
        (relay_x + 25, relay_y + 9),
        (relay_x + 5, relay_y + 9),
        (relay_x + 5, relay_y + 7),
    ])
    program.pipe([
        (relay_x + 9, relay_y - 1),
        (relay_x + 9, bottom + 6),
        (relay_x + 22, bottom + 6),
        (relay_x + 22, bottom + 4),
        (ports["rr"][0], bottom + 4),
        ports["rr"],
    ])
    return {
        "ports": ports,
        "bottom": bottom,
        "layout": layout,
        "relay_bottom": relay_y + 7,
    }


def build():
    program = lm.Program()
    add_service(program, with_io=True)
    return program


def reference(commands):
    ring = [0] * SLOTS
    cursor = 0
    output = []
    for command in commands:
        mode = command[0]
        output.append(mode)
        if mode > 0:
            takes = command[1:]
            assert len(takes) == SLOTS
            for take in takes:
                ring[cursor] |= take
                cursor = (cursor + 1) % SLOTS
        elif mode < 0:
            masks = command[1:]
            assert len(masks) == SLOTS
            for mask in masks:
                output.append(ring[cursor] & mask)
                cursor = (cursor + 1) % SLOTS
        else:
            ring = [0] * SLOTS
            cursor = 0
    return output, ring


def run(commands):
    values = [value for command in commands for value in command]
    expected, ring = reference(commands)
    result = subprocess.run(
        [
            LM,
            "--grade",
            OUT,
            "--cap=50000",
            "--input=" + " ".join(map(str, values)),
            "--expected=" + " ".join(map(str, expected)),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"status":"pass"' in result.stdout, (result.stdout, commands, expected)
    return ring


def main():
    program = build()
    program.save(OUT)

    rng = random.Random(0x51A7E)
    commands = []
    for _ in range(2):
        commands.append([1] + [rng.randrange(65536) for _ in range(SLOTS)])
    masks = [0] * SLOTS
    masks[4 * 7:4 * 7 + 4] = [1 << 11] * 4
    commands.append([-1] + masks)
    commands.append([0])
    commands.append([-1] + masks)
    commands.append([1] + [rng.randrange(65536) for _ in range(SLOTS)])
    commands.append([-1] + [1 << (index % 16) for index in range(SLOTS)])
    run(commands)

    print("PASS resettable/queryable parent ring")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
