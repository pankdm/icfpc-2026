#!/usr/bin/env python3
"""Pack Pathfinder's 256 setup bits into sixteen unsigned row words.

The packer keeps the current row in B and uses the identity

    2 * acc + (1 - wall)
      = (((wall - acc) negated) + acc), then add one through W

so each input bit costs only ``r-N+W1+M`` plus the loop counter.  A separate
acknowledger sees every completed row through S and returns 1 for rows 0..14,
then 0 for row 15.  That final zero moves the packer to coordinate mode before
it can accidentally consume rx/ry as maze bits.

This is deliberately a standalone measured gadget.  It outputs the sixteen
OPEN words followed by rx and ry so the protocol can be checked directly by
the Rust interpreter before it is attached to the wavefront core.
"""

import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-setup-packer.man"


def build():
    p = lm.Program()

    # Input directly above the packer's bit receive port.
    p.input_room(8, 0)

    # Packer.  The top row contains the hot bit loop.  BP>0 turns down at d
    # into the short return loop; BP=0 continues to S/r/X.
    px, py = 0, 10
    p.room(px, py, 34, 12)
    p.text(px + 1, py + 1, "@8M+b0Mv")
    p.text(px + 8, py + 3, ">r-N+W1+MmdSrXRSRSH")
    p.put(px + 18, py + 7, "<")
    p.put(px + 8, py + 7, "^")

    # Ack=1 descends from X and resets BP=16 and B=0 before re-entering
    # the bit loop.  Ack=0 goes straight into the two coordinate receives.
    p.put(px + 21, py + 9, "<")
    p.text(px + 20, py + 9, "8M+b0M", d="W")
    p.put(px + 8, py + 9, "^")

    # Static input pipe.  It is nearest to the hot r at x=8.  Coordinate mode
    # uses R because the (nearer) ack pipe is empty after the final ack.
    p.pipe([(9, 3), (9, 9)])

    # Output relay receives every S broadcast and is the sole output source.
    ox, oy = 39, 10
    p.room(ox, oy, 8, 6)
    p.text(ox + 1, oy + 1, "@>rsv")
    p.put(ox + 5, oy + 3, "<")
    p.put(ox + 2, oy + 3, "^")
    p.output_room(53, 10)
    p.pipe([(34, py + 3), (38, py + 3)])
    p.pipe([(47, oy + 2), (52, oy + 2)])

    # Ack counter.  It receives the same row through S, decrements BP=16,
    # and sends 1 while BP remains positive, otherwise sends 0 and halts.
    ax, ay = 0, 27
    p.room(ax, ay, 22, 11)
    p.text(ax + 1, ay + 1, "@8M+bv")
    p.text(ax + 6, ay + 3, ">rmd0sH")
    p.put(ax + 9, ay + 7, ">")
    p.text(ax + 10, ay + 7, "1s")
    p.put(ax + 19, ay + 7, "^")
    p.put(ax + 19, ay + 5, "<")
    p.put(ax + 6, ay + 5, "^")

    # Second branch of the packer's S broadcast.
    p.pipe([
        (19, py + 12),
        (19, ay - 3),
        (7, ay - 3),
        (7, ay - 1),
    ])
    # Ack reply is closer to the packer's r at x=19 than the static input is.
    p.pipe([(20, ay - 1), (20, py + 12)])

    return p


def row_word(walls, row):
    value = 0
    for wall in walls[16 * row:16 * (row + 1)]:
        value = 2 * value + (1 - wall)
    return value


def run_case(walls, rx, ry):
    expected = [row_word(walls, row) for row in range(16)] + [rx, ry]
    args = [
        LM,
        "--grade",
        OUT,
        "--cap=20000",
        "--input=" + " ".join(map(str, walls + [rx, ry])),
        "--expected=" + " ".join(map(str, expected)),
    ]
    result = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip(), expected


def main():
    program = build()
    program.save(OUT)

    cases = [
        ([0] * 256, 1, 1),
        ([1] * 256, 14, 14),
        ([index & 1 for index in range(256)], 3, 12),
    ]
    rng = random.Random(0xB17)
    for _ in range(20):
        cases.append(([rng.randrange(2) for _ in range(256)],
                      rng.randrange(16), rng.randrange(16)))

    for index, (walls, rx, ry) in enumerate(cases):
        result, expected = run_case(walls, rx, ry)
        assert '"status":"pass"' in result, (index, result, expected)

    print(f"PASS setup packer ({len(cases)} cases)")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
