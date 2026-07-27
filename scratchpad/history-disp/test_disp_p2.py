#!/usr/bin/env python3
"""Standalone semantic test for the history-lesson dispatcher room.

Runs the DISP grid on its own -- no feeder, no P1, no oracle -- against a
scripted symbol stream and a scripted dictionary ring, and checks that

  * every symbol produces the right value on the UNPACK port, and
  * the ring comes back in canonical order.

Both the shipped `build_vertical_p1` grid (23x9 interior) and the compacted
`build_vertical_p2` grid (21x5 interior) are checked, so the compaction is
pinned to the behaviour it replaced.

    python3 scratchpad/history-disp/test_disp_p2.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [HERE, os.path.join(ROOT, "solutions", "history-lesson"),
                os.path.join(ROOT, "tools")]

from simtest import check                     # noqa: E402
import build_ring as base                     # noqa: E402
import build_vertical_p1 as p1                # noqa: E402
import build_vertical_p2 as p2                # noqa: E402

# Ports are local interior coordinates of the cell the pipe attaches with --
# one cell outside the wall, which is what nearest-pipe distance measures to.
# west: x = -2   north: y = -2   south: y = height + 1
CASES = [
    ("p1 dispatcher 23x9", list(p1.DISP_NARROW_ROWS), (1, 0), [
        ("stream", "in", (-2, 1)),
        ("ring", "in", (17, 7)),
        ("unpack", "out", (17, -5)),   # 3 countdown rows sit above the logic
        ("ring", "out", (21, 7)),
    ]),
    ("p2 dispatcher 21x5", list(p2.DISP_ROWS), (1, 0), [
        ("stream", "in", (-2, 1)),
        ("ring", "in", (p2.RING_IN_PORT - p2.DISP_X - 1, 6)),
        ("unpack", "out", (p2.UNPACK_PORT - p2.DISP_X - 1, -2)),
        ("ring", "out", (p2.RING_OUT_PORT - p2.DISP_X - 1, 6)),
    ]),
]

# The 81x81 champion's dispatcher also has to forward the 0 year marker, and
# both of its ring legs attach to the east wall.  Ports read off the built
# layout: DISP interior is x=51..71, y=66..70.
CHAMPION = [
    ("81x81 dispatcher 24x6 (was)", list(base.DISP_ROWS), (1, 0), [
        ("stream", "in", (-2, 2)),
        ("ring", "in", (25, 5)),
        ("year", "out", (-2, 0)),
        ("ring", "out", (25, -1)),
    ]),
    ("81x81 dispatcher 21x5 (now)", list(base.DISP_COMPACT_ROWS), (1, 0), [
        ("stream", "in", (-2, 2)),
        ("ring", "in", (22, 4)),
        ("year", "out", (-2, 0)),
        ("ring", "out", (22, 0)),
    ]),
]


def main():
    failed = 0
    for name, rows, start, ports in CASES:
        for seed in (7, 11, 23):
            why = check(rows, ports, start=start, seed=seed)
            if why:
                print(f"FAIL {name} seed={seed}: {why}")
                failed += 1
                break
        else:
            print(f"ok   {name}")
    for name, rows, start, ports in CHAMPION:
        ports = [("unpack" if q == "year" else q, k, a) for q, k, a in ports]
        for seed in (7, 11, 23):
            why = check(rows, ports, start=start, seed=seed,
                        entries=38, zeros=True)
            if why:
                print(f"FAIL {name} seed={seed}: {why}")
                failed += 1
                break
        else:
            print(f"ok   {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
