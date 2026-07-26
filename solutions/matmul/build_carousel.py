#!/usr/bin/env python3
"""Carousel matmul — incremental builder.

Stages (each independently gradable, so the machine is verified as it grows):
  hdr     read N,M,K and emit N*M            -- controller arithmetic + I/O
  seedA   read N,M,K then N*M values into the A-ring, then drain it to output
  seedB   as seedA, then M*K values into the b-ring, drain b-ring to output

Design: docs/matmul-carousel-design.md.  Probed facts that shape this file:
  * `s` preserves A, `*` preserves B          (scratchpad/mm_probe.py)
  * a pipe may NOT connect a room to itself   -> every ring needs a relay room
"""
import argparse
import os
import subprocess
import sys

REPO = os.path.abspath(__file__).split("/solutions/")[0]
sys.path.insert(0, REPO + "/tools")
import littleman as lm  # noqa: E402

LM = REPO + "/interp/target/release/lm"


def relay(p, x, y):
    """6x4 relay room running an 8-cell shuttle loop.

        +----+
        |>@rv|
        |^.s<|
        +----+

    The cell the loop re-enters heading NORTH must be a `>` to turn east again,
    so `@` cannot live there -- the man starts one cell along instead.  Returns
    the (r_cell, s_cell) coordinates for pipe placement.
    """
    p.room(x, y, 6, 4)
    p.text(x + 1, y + 1, ">@rv")
    p.text(x + 1, y + 2, "^.s<")
    return (x + 3, y + 1), (x + 3, y + 2)


def build_hdr():
    """r N, M(B=N), r M, * -> A=N*M, s."""
    p = lm.Program()
    p.room(0, 0, 9, 3)
    p.text(1, 1, "@rMr*s")
    p.input_room(0, 5)
    p.output_room(5, 5)
    p.pipe([(1, 4), (1, 3)], end_direction="N")     # I -> ctrl (bottom wall)
    p.pipe([(6, 3), (6, 4)], end_direction="S")     # ctrl -> O
    return p


def build_ring():
    """Ring echo: read a value, push it round a relay ring, read it back, emit.

    Proves the ring primitive that every store in this machine is built from.
    Pipe placement is chosen so nearest-pipe binding is unambiguous:
      incoming: input@(5,1)  ring-in@(9,7)
      outgoing: output@(20,5) ring-out@(8,7)
    """
    p = lm.Program()
    p.room(6, 0, 14, 7)                       # controller x=6..19 y=0..6
    p.text(7, 1, "@r")                        # @ then r(input)
    p.put(9, 1, "v")
    p.put(9, 2, "s")                          # -> ring-out (dist 6 vs 14)
    p.put(9, 3, ".")
    p.put(9, 4, "r")                          # <- ring-in  (dist 3 vs 7)
    p.put(9, 5, ">")
    for x in range(10, 18):
        p.put(x, 5, ".")
    p.put(18, 5, "s")                         # -> output   (dist 2 vs 12)

    p.input_room(0, 0)
    p.output_room(22, 4)
    p.pipe([(3, 1), (5, 1)])                  # I -> ctrl (left wall)
    p.pipe([(20, 5), (21, 5)])                # ctrl -> O (right wall)

    relay(p, 6, 9)                            # relay x=6..10 y=9..12
    p.pipe([(8, 7), (8, 8)], end_direction="S")   # ctrl -> relay
    p.pipe([(9, 8), (9, 7)], end_direction="N")   # relay -> ctrl
    return p


def build_loop():
    """Counted loop: read n, then echo the next n values.

    The loop primitive the whole machine is built from:
        `b` sets BP=n, the body runs, `m` decrements BP, `d` turns CLOCKWISE
        while BP>0 and falls straight through when it hits 0.
    Heading east at `d`, a turn goes south into the return path; the fall-through
    continues east to the exit.
    """
    p = lm.Program()
    p.room(5, 0, 13, 7)                     # ctrl x=5..17 y=0..6
    p.text(6, 1, "@rbv")                    # read n, BP=n, turn south
    p.put(9, 2, ".")
    p.text(9, 3, ">rsmd")                   # body: r(in) s(out) m d
    p.put(14, 3, "H")                       # BP==0 -> fall through and halt
    p.put(13, 4, "<")
    p.text(10, 4, "...")
    p.put(9, 4, "^")

    p.input_room(0, 0)
    p.output_room(20, 2)
    p.pipe([(3, 1), (4, 1)])                # I -> ctrl
    p.pipe([(18, 3), (19, 3)])              # ctrl -> O
    return p


def build_seedA():
    """Read N,M,K; push N*M input values into the A-ring; drain it to output.

    Proves the storage path end to end.  Trick that removes the need for a second
    'variable' ring: N*M is pushed into the ring as its FIRST value, so the drain
    phase recovers its own loop count by reading it back.

    Pipe attachment (all on the ctrl top wall, so nearest-binding is by column):
        input  @x=8   dataOut @x=10 (outgoing)   dataIn @x=20 (incoming)
        output on the right wall @y=9
    """
    p = lm.Program()
    p.room(5, 6, 20, 8)                        # ctrl x=5..24 y=6..13
    relay(p, 14, 0)                            # relay x=14..19 y=0..3

    # --- phase 1: N,M -> NM ; BP=NM ; push NM ; discard K
    p.text(6, 7, "@rMr*b")                     # A=N, B=N, A=M, A=NM, BP=NM
    p.put(12, 7, "v")
    p.put(12, 8, "<")
    p.put(11, 8, ".")
    p.put(10, 8, "s")                          # push NM into the ring
    p.put(9, 8, "r")                           # read K, discard
    p.put(8, 8, "v")
    p.put(8, 9, ">")
    # --- phase 2: loop NM times, input -> ring
    p.text(9, 9, "rsmd")                       # r(in) s(ring) m d
    p.put(12, 10, "<")
    p.text(9, 10, "...")
    p.put(8, 10, "^")
    # --- phase 3: recover the count, then drain the ring to output
    p.text(13, 9, ".......")                   # walk east to the dataIn side
    p.put(20, 9, "r")                          # A = NM (first value back)
    p.put(21, 9, "b")                          # BP = NM
    p.put(22, 9, "v")
    p.put(22, 10, "<")
    p.text(20, 10, "..")
    p.put(19, 10, "v")
    p.put(19, 11, ">")
    p.text(20, 11, "rsmd")                     # r(ring) s(out) m d
    p.put(23, 12, "<")
    p.text(20, 12, "...")
    p.put(19, 12, "^")

    p.input_room(0, 0)
    p.output_room(28, 8)
    p.pipe([(3, 1), (8, 1), (8, 5)], end_direction="S")     # I -> ctrl
    p.pipe([(10, 5), (10, 4), (15, 4)], end_direction="N")  # ctrl -> relay
    # NOTE: a pipe attaches to its SOURCE room via the backward neighbour of its
    # first cell, taken along the FIRST SEGMENT's direction.  So a pipe leaving a
    # room's bottom wall must head SOUTH first; starting east attaches to nothing
    # and every `s` in that room dies with `no-pipe`.
    p.pipe([(17, 4), (17, 5), (20, 5)], end_direction="S")  # relay -> ctrl
    p.pipe([(25, 9), (27, 9)])                              # ctrl -> O
    return p


def grade(p, name, inp, exp, cap=5000):
    out = ("/private/tmp/claude-502/-Users-dmitrykorolev-projects-icfpc-2026/"
           "0580956d-53cb-4ded-b43a-408e532171a2/scratchpad")
    path = f"{out}/{name}.man"
    p.save(path)
    r = subprocess.run([LM, "--grade", path, f"--input={inp}",
                        f"--expected={exp}", f"--cap={cap}"],
                       capture_output=True, text=True)
    print(f"  {name:<10} in=[{inp}] exp=[{exp}] -> {r.stdout.strip()[:150]}")
    return r.stdout


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="hdr")
    ap.add_argument("--out")
    a = ap.parse_args()
    p = {"hdr": build_hdr}[a.stage]()
    if a.out:
        p.save(a.out)
        print("saved", a.out, "footprint", p.footprint())
    else:
        grade(p, a.stage, "2 3 4", "6")
