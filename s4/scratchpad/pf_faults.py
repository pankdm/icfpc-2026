#!/usr/bin/env python3
"""Explain the faults of one (ports, floor) config in terms of PIPES, not cells.

A collision report like ``(84, 202, '-', '|', 'pipe')`` says nothing about which
two services fight over that cell.  This maps every fault back to the pipe index
and the port names, which is what tells you WHICH component to move.

    cd s4 && python3 scratchpad/pf_faults.py /tmp/pf_out_31.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import build_rail  # noqa: E402
import manlint  # noqa: E402
import stateflow  # noqa: E402

# emission order of stateflow.build_program's non-compact floor
PIPE_NAMES = ["ri", "sp(scratch in)", "rp(scratch out)", "sc(scalar cmd)",
              "rr(scalar reply)", "cc(packed cmd)", "packed->cell cmd",
              "cr(cell reply)", "sa(display addr)", "sd(display data)",
              "ss(display swap)", "qs(queue push)", "qr(queue return)"]


def main(path):
    blob = json.load(open(path))
    ports = {n: stateflow.DEFAULT_PORTS[n][0] for n in stateflow.DEFAULT_PORTS}
    ports.update(blob["ports"])
    floor = dict(blob["floor"])
    qrows = floor.pop("queue_rows", 1)
    qright = floor.pop("queue_right_off", 300)
    spec = {n: (ports[n], stateflow.DEFAULT_PORTS[n][1]) for n in ports}
    program, layout = build_rail.build(
        verify=False, ports=spec, floor=floor, queue_rows=qrows,
        queue_right_off=qright)
    print("footprint", program.footprint(), "controller",
          layout["width"], "x", layout["height"], "bottom", layout["bottom"])
    print("ports", dict(sorted(ports.items(), key=lambda kv: kv[1])))
    print("\npipes:")
    for i, (first, last, n, back, fwd) in enumerate(program.pipes):
        name = PIPE_NAMES[i] if i < len(PIPE_NAMES) else f"#{i}"
        print(f" {i:2d} {name:22s} {first} -> {last} len {n} "
              f"back {back}={program.get(*back)!r} fwd {fwd}={program.get(*fwd)!r}")
    print("\ncollisions:")
    for o in manlint.bad_overwrites(program):
        print("  ", o)
    print("buried under a room wall:", manlint.room_over_pipe(program)[:8])
    print("dangling:", manlint.dangling_pipes(program))


if __name__ == "__main__":
    main(sys.argv[1])
