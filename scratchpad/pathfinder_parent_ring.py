#!/usr/bin/env python3
"""Pathfinder canonical 16-word parent ring.

The four 64-bit lanes need 4 directions x 4 words of parent state.  Those
values are updated in one fixed order on every BFS layer, so sixteen persistent
accumulator rooms are unnecessary: a single rotating FIFO is the natural
register file.

This probe seeds sixteen zero words once, then consumes two layers of sixteen
TAKE masks.  For every mask it pops the next parent word, ORs the mask, and
pushes the word back.  At quiescence the ring must contain exactly the sixteen
direction/word accumulators.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-parent-ring.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")
SLOTS = 16


def build():
    p = lm.Program()

    # Input supplies TAKE masks in canonical direction-major, word-minor order.
    p.input_room(20, 0)

    # Initialisation loop:
    #   BP=16; A=0; send zero, decrement, loop while BP>0.
    # Processing loop:
    #   read TAKE -> B; read parent -> OR; push updated parent.
    p.room(0, 5, 43, 5)
    p.text(1, 6, ">@8M+b0")
    p.text(8, 6, ">smd")
    p.put(11, 7, "<")
    p.put(8, 7, "^")
    p.put(20, 6, ">")
    p.text(21, 6, "rM")
    p.text(35, 6, "r|s")
    p.put(40, 6, "v")
    p.put(40, 7, "<")
    p.put(20, 7, "^")

    # Data-driven relay closes the FIFO ring.
    p.room(32, 14, 10, 5)
    p.text(33, 15, ">@rs")
    p.put(39, 15, "v")
    p.put(39, 16, "<")
    p.put(33, 16, "^")

    p.pipe([(21, 3), (21, 4)])                  # input -> updater
    p.pipe([(37, 10), (37, 13)])                # updater -> relay
    p.pipe([(42, 15), (45, 15), (45, 6), (43, 6)])  # relay -> updater
    return p


def inspect(values, tick=2000):
    program = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT, f"--input={' '.join(map(str, values))}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), program


def ring_values(snapshot):
    values = []
    for pipe in snapshot["pipes"]:
        for item in pipe.get("values") or []:
            values.append(item["value"])

    # When the return pipe is full, the relay can be parked on its send with
    # one additional ring token in A.
    relay = snapshot["runners"][1]
    if len(values) < SLOTS:
        values.append(relay["a"])
    assert len(values) == SLOTS, (len(values), values, snapshot)
    return values


def main():
    layers = [
        [(i + 1) * 0x101 for i in range(SLOTS)],
        [1 << (32 + i) for i in range(SLOTS)],
    ]
    layers[1][-1] = -(1 << 63)
    # Convert unsigned test constants to signed i64 input spellings.
    for layer in layers:
        for i, value in enumerate(layer):
            if value >= 1 << 63:
                layer[i] = value - (1 << 64)

    expected = [0] * SLOTS
    for layer in layers:
        expected = [a | b for a, b in zip(expected, layer)]

    snap, program = inspect([value for layer in layers for value in layer])
    assert snap.get("end") not in ("loaderror", "fatal"), snap
    got = ring_values(snap)
    assert sorted(got) == sorted(expected), (got, expected, snap)
    print("PASS canonical 16-word parent ring")
    print("expected:", expected)
    print("ring:", got)
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
