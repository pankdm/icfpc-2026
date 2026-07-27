#!/usr/bin/env python3
"""Port-specific row assembler for the parallel Pathfinder feed.

Unlike ``pathfinder_row_assembler.py`` (an arithmetic/interval probe using one
ordered input pipe), this gadget proves five independent nearest-input ports:
state, U, self-for-R, self-for-L, and D.  The real row splitter and ``@rS``
frontier relays can therefore feed all sixteen assemblers concurrently.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-row-assembler-ports.man"


def ported_assembler(program, x, y):
    # Deliberately spacious port proof.  The 18×10 one-pipe arithmetic probe
    # measures the tight interval; this room isolates binding correctness.
    program.room(x, y, 30, 8)
    right = x + 28
    bottom = y + 6
    program.put(x + 1, y + 1, ">")
    program.put(x + 2, y + 1, "@")

    # Top ports: state, U, self-R, self-L.
    for dx, op in [
        (3, "r"), (4, "s"),
        (9, "r"), (10, "s"),
        (15, "r"), (16, "M"), (17, "+"), (18, "s"),
        (21, "r"),
    ]:
        program.put(x + dx, y + 1, op)
    program.put(right, y + 1, "v")

    # Finish L down the right side.
    for dy, op in enumerate(["M", "2", "W", "/"], start=2):
        program.put(right, y + dy, op)
    program.put(right, bottom, "<")

    # Bottom ports: emit L, receive D, emit D.
    program.put(x + 23, bottom, "s")
    program.put(x + 22, bottom, "r")
    program.put(x + 21, bottom, "s")
    program.put(x + 1, bottom, "^")


def _source_bank(program, y, ports, values):
    """Independent constant-source rooms aligned to well-spaced top ports."""
    for port_x, value in zip(ports, values):
        program.room(port_x - 2, y, 5, 6)
        program.put(port_x - 1, y + 1, "@")
        program.put(port_x, y + 1, "v")
        program.put(port_x, y + 2, str(value))
        program.put(port_x, y + 3, "s")
        program.put(port_x, y + 4, "H")


def build():
    program = lm.Program()
    x, y = 20, 20
    ported_assembler(program, x, y)

    top_ports = [x + 3, x + 9, x + 15, x + 21]
    _source_bank(program, 5, top_ports, [7, 2, 3, 3])
    for port_x in top_ports:
        program.pipe([(port_x, 11), (port_x, y - 1)])

    # D source below the room.
    d_x = x + 22
    program.room(d_x - 1, y + 12, 6, 5)
    program.put(d_x, y + 15, "@")
    program.put(d_x + 1, y + 15, "4")
    program.put(d_x + 2, y + 15, "s")
    program.put(d_x + 3, y + 15, "H")
    program.pipe([
        (d_x + 1, y + 11),
        (d_x + 1, y + 9),
        (d_x, y + 9),
        (d_x, y + 8),
    ])

    program.output_room(x + 33, y + 2)
    program.pipe([(x + 30, y + 3), (x + 32, y + 3)])
    return program


def main():
    program = build()
    program.save(OUT)
    result = subprocess.run(
        [
            LM,
            "--grade",
            OUT,
            "--cap=10000",
            "--expected=7 2 6 1 4",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"status":"pass"' in result.stdout, result.stdout
    print("PASS five-port row-local assembler")
    print(result.stdout.strip())
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
