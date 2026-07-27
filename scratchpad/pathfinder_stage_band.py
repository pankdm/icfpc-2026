#!/usr/bin/env python3
"""Sixteen-lane Pathfinder priority-stage band probe.

The competitor score decomposition suggests a 138--154-cell lane machine.  A
row of adjacent rooms holds sixteen independent row workers at a nine-column
pitch. This probe validates the geometry and nearest-pipe binding with
distinct per-lane values. Multiple initial ``@`` men in one shared room are
load-invalid; a shared hall would require a runtime ``Y`` splitter.

Each worker consumes STATE and CANDIDATE and emits one canonical stream:

    reduced_state, take

Later priority bands can append earlier TAKE tokens to the same stream.  This
is the physical pipe-pair deletion that makes a 16-row layout plausible.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-stage-band.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")
LANES = 16
PITCH = 9
WIDTH = LANES * PITCH


def build():
    p = lm.Program()

    # Sixteen setup sources. Adjacent rooms share no cells; each emits two
    # values through columns matching its worker's receive sites.
    for lane in range(LANES):
        x = lane * PITCH
        base = x + 1
        state = 9 - lane % 7
        candidate = 1 + lane % 7
        p.room(x, 0, PITCH, 4)
        p.put(base, 1, "@")
        p.put(base + 1, 1, str(state))
        p.put(base + 2, 1, "s")
        p.put(base + 3, 1, str(candidate))
        p.put(base + 4, 1, "s")
        p.put(base + 5, 1, "H")

    # Sixteen adjacent nine-column rooms. The second row returns through the
    # leading '>' cell, so no worker can walk into a wall.
    for lane in range(LANES):
        x = lane * PITCH
        p.room(x, 6, PITCH, 4)
        p.text(x + 1, 7, ">@rMr&v")
        p.put(x + 7, 8, "<")
        p.put(x + 6, 8, "W")
        p.put(x + 5, 8, "~")
        p.put(x + 4, 8, "s")   # reduced state
        p.put(x + 3, 8, "W")
        p.put(x + 2, 8, "s")   # take
        p.put(x + 1, 8, "^")

        # STATE and CANDIDATE.
        p.pipe([(x + 3, 4), (x + 3, 5)])
        p.pipe([(x + 5, 4), (x + 5, 5)])

    # Per-lane sinks consume the two-token output stream and retain
    # B=reduced_state, A=take while parked on the next receive.
    for lane in range(LANES):
        x = lane * PITCH
        base = x + 1
        p.room(x, 12, PITCH, 4)
        p.text(base, 13, ">@rMrv")
        p.put(base + 5, 14, "<")
        p.put(base, 14, "^")
        p.pipe([(x + 3, 10), (x + 3, 11)])
    return p


def inspect(tick=100):
    program = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), program


def main():
    snapshot, program = inspect()
    assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot
    runners = sorted(snapshot["runners"], key=lambda runner: runner["id"])
    # Sources halt first, then the sixteen stage workers and sixteen sinks.
    sinks = runners[-LANES:]
    for lane, runner in enumerate(sinks):
        state = 9 - lane % 7
        candidate = 1 + lane % 7
        take = state & candidate
        assert runner["b"] == state ^ take, (lane, runner, snapshot)
        assert runner["a"] == take, (lane, runner, snapshot)
    print(f"PASS {LANES} lanes at pitch {PITCH}")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
