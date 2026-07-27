#!/usr/bin/env python3
"""Persistent unsigned-row Pathfinder tile.

This closes the protocol between the pieces that had previously only been
tested separately:

* one UNVIS word circulates through U/R/D/L priority stages;
* the four TAKE values are merged in direction order and broadcast once;
* NEXT ORs the same four values;
* a canonical four-word parent ring updates U/R/D/L in lockstep.

The probe queues two complete layers before execution.  It checks both NEXT
outputs with the Rust grader, then inspects the persistent UNVIS and parent
state.  Candidate generation and the sixteen-row barrier are deliberately
outside this tile.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-row-tile.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")


def return_loop(p, left, right, y):
    p.put(right, y, "v")
    p.put(right, y + 1, "<")
    p.put(left, y + 1, "^")


def build():
    p = lm.Program()

    # Input order is:
    #   initial_unvisited,
    #   U_layer0, U_layer1, R_layer0, R_layer1, ... L_layer1.
    # Grouping by direction lets a straight dispatcher queue two values on
    # each candidate pipe before the stages start consuming them.
    p.input_room(44, -9)
    p.room(0, -4, 90, 7)
    p.put(1, -3, ">")
    p.put(2, -3, "@")
    for x, ch in (
        (3, "r"), (4, "s"),
        (6, "r"), (7, "s"), (8, "r"), (9, "s"),
        (29, "r"), (30, "s"), (31, "r"), (32, "s"),
        (52, "r"), (53, "s"), (54, "r"), (55, "s"),
        (75, "r"), (76, "s"), (77, "r"), (78, "s"),
        (82, "H"),
    ):
        p.put(x, -3, ch)
    p.pipe([(45, -6), (45, -5)])

    # Four priority stages. State moves left-to-right; each stage consumes its
    # already-queued candidate and emits TAKE downward.
    stage_x = (0, 23, 46, 69)
    candidate_x = (8, 31, 54, 77)
    for index, x in enumerate(stage_x):
        p.room(x, 10, 21, 5)
        p.put(x + 1, 11, ">")
        p.text(x + 2, 11, "@rM")
        p.put(x + 8, 11, "r")
        p.text(x + 9, 11, "&sW~WW")
        p.put(x + 17, 11, "s")
        return_loop(p, x + 1, x + 18, 11)
        if index < 3:
            p.pipe([(x + 21, 11), (x + 22, 11)])

    # Queue both candidates for each stage on one physical pipe.
    for sx, cx in zip((8, 31, 54, 77), candidate_x):
        p.pipe([(sx, 3), (sx, 9)])

    # A two-input relay seeds the circulating UNVIS state, then accepts the
    # reduced state from L for every later layer. Stage U sees one input pipe.
    p.room(92, 8, 10, 5)
    p.text(93, 9, ">@Rsv")
    p.put(97, 10, "<")
    p.put(93, 10, "^")
    p.pipe([
        (4, 3), (4, 4), (-1, 4),
        (-1, -10), (94, -10), (94, 7),
    ])
    p.pipe([
        (90, 11), (91, 11), (91, 7),
        (89, 7), (89, 9), (91, 9),
    ])
    # Return outside the whole tile. A route through the setup apron crosses
    # all four queued-candidate pipes.
    p.pipe([
        (102, 9), (105, 9), (105, -12),
        (-3, -12), (-3, 11), (-1, 11),
    ])

    # Ordered TAKE collector. The stage chain guarantees only one direction is
    # ready at a time, but distinct lowercase sites also make the ordering
    # explicit. Every TAKE leaves on the collector's sole outgoing pipe.
    p.room(0, 20, 89, 5)
    p.put(1, 21, ">")
    p.put(2, 21, "@")
    for x in (10, 33, 56, 79):
        p.text(x, 21, "rs")
    return_loop(p, 1, 85, 21)
    for x in (10, 33, 56, 79):
        p.pipe([(x, 15), (x, 19)])

    # Relay broadcasts the ordered TAKE stream to NEXT and the parent updater.
    p.room(40, 28, 12, 5)
    p.text(41, 29, ">@rSv")
    p.put(45, 30, "<")
    p.put(41, 30, "^")
    p.pipe([(45, 25), (45, 27)])

    # Parent ring updater. Seed four zero words once, then:
    #   TAKE -> B; parent -> A; A|B; send updated parent.
    p.room(0, 38, 43, 5)
    p.text(1, 39, ">@4b0")
    p.text(8, 39, ">smd")
    p.put(11, 40, "<")
    p.put(8, 40, "^")
    p.put(20, 39, ">")
    p.text(21, 39, "rM")
    p.text(35, 39, "r|s")
    p.put(40, 39, "v")
    p.put(40, 40, "<")
    p.put(20, 40, "^")

    p.room(32, 47, 10, 5)
    p.text(33, 48, ">@rs")
    p.put(39, 48, "v")
    p.put(39, 49, "<")
    p.put(33, 49, "^")
    p.pipe([(44, 33), (44, 35), (21, 35), (21, 37)])
    p.pipe([(37, 43), (37, 46)])
    p.pipe([(42, 48), (45, 48), (45, 39), (43, 39)])

    # NEXT sees the same ordered stream. Four unrolled receives make the layer
    # boundary structural; after the fourth OR it emits the complete word.
    p.room(52, 38, 27, 5)
    p.put(53, 39, ">")
    p.text(54, 39, "@0M")
    p.text(57, 39, "r|Mr|Mr|Mr|M")
    p.text(69, 39, "s0M")
    return_loop(p, 53, 73, 39)
    p.pipe([(48, 33), (48, 35), (57, 35), (57, 37)])

    p.output_room(83, 37)
    p.pipe([(69, 37), (69, 34), (84, 34), (84, 36)])
    return p


def inspect(values, tick=3000):
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
    return values


def main():
    layers = [
        [0x0F0F, 0x00FF, 0x3333, 0x5555],
        [0x0FF0, 0x0F0F, 0x3333, 0xAAAA],
    ]
    initial = 0xFFFF
    remaining = initial
    parents = [0, 0, 0, 0]
    next_words = []
    for layer in layers:
        nxt = 0
        for direction, candidate in enumerate(layer):
            take = remaining & candidate
            remaining ^= take
            parents[direction] |= take
            nxt |= take
        next_words.append(nxt)

    values = [initial]
    for direction in range(4):
        values.extend(layer[direction] for layer in layers)

    snapshot, program = inspect(values)
    assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot
    output = snapshot.get("output") or []
    assert output == next_words, (output, next_words, snapshot)

    runners = sorted(snapshot["runners"], key=lambda runner: runner["id"])
    # dispatcher, four stages, state relay, collector, fanout, parent updater,
    # parent relay, NEXT. Stage L retains the latest completed UNVIS in A while
    # it waits for the next state word.
    got_unvisited = runners[4]["a"]
    assert got_unvisited == remaining, (got_unvisited, remaining, snapshot)

    # Ring order may rotate while quiescent; compare as multisets. Values can
    # also be parked in the relay/updater registers rather than pipe cells.
    candidates = ring_values(snapshot)
    candidates.extend(runner["a"] for runner in runners[8:10])
    for value in parents:
        assert value in candidates, (value, candidates, snapshot)

    print("PASS two persistent row layers")
    print("NEXT:", next_words)
    print("UNVIS:", remaining)
    print("PARENTS:", parents)
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
