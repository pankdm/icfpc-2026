"""Generate a two-room, pipe-backed solution for the memory problem.

The memory is a circulating FIFO containing 100 encoded cell values followed by
a negative sentinel.  Addresses are implicit positions in that stream.  A small
relay room closes the FIFO because Littleman forbids a pipe from returning to the
same room.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import littleman as lm


CELL_COUNT = 100
VALUE_OFFSET = 2_000_000
SENTINEL = -1


def build_simple_pipe_memory() -> lm.Program:
    program = lm.Program()

    controller_right = 29
    controller_bottom = 28
    program.room(0, 0, controller_right + 1, controller_bottom + 1)

    _place_initializer(program)
    _place_operation_loop(program)

    program.input_room(1, controller_bottom + 5)
    program.pipe([(2, controller_bottom + 4), (2, controller_bottom + 1)])

    program.output_room(27, controller_bottom + 5)
    program.pipe([(28, controller_bottom + 1), (28, controller_bottom + 4)])

    _place_storage_belt(program, controller_bottom)
    return program


def _place_initializer(program: lm.Program) -> None:
    """Seed the belt with 100 encoded zeroes and one sentinel."""
    program.put(1, 1, "@")
    program.text(2, 1, f"`{CELL_COUNT}`")
    backpack_x = 2 + len(str(CELL_COUNT)) + 2
    program.put(backpack_x, 1, "b")
    # Starting from A=100: 100*100*100=1,000,000, then double it.
    program.text(backpack_x + 1, 1, "M**M2*")

    turn_x = backpack_x + 7
    program.put(turn_x, 1, "v")
    program.put(turn_x, 3, "<")

    program.put(9, 2, ">")
    program.put(10, 2, "s")
    program.put(11, 2, "m")
    program.put(12, 2, "v")
    program.put(12, 3, "<")
    program.put(9, 3, "d")

    program.put(1, 3, "v")
    program.put(1, 4, ">")
    program.put(2, 4, str(abs(SENTINEL)))
    program.put(3, 4, "N")
    program.put(10, 4, "s")
    program.put(11, 4, "v")
    program.put(11, 5, "<")
    program.put(2, 5, "v")


def _place_operation_loop(program: lm.Program) -> None:
    """Read operations, rotate to the addressed cell, service it, and realign."""
    # Read op into B and address into BP.
    program.put(2, 6, "r")
    program.put(2, 7, "M")
    program.put(2, 8, "r")
    program.put(2, 9, "b")
    program.put(2, 10, ">")
    program.put(12, 10, "^")
    program.put(12, 6, ">")
    program.put(27, 6, "^")
    program.put(27, 4, "<")
    program.put(17, 4, "v")

    # Rotate BP cells four at a time. The direction-only perimeter merges all
    # four zero-count exits into the southbound path at (20, 14).
    scan_rows = (
        "v<      ",
        "vdsm>rdv",
        "vr    sv",
        "vm    mv",
        "v^    vv",
        "vs    rv",
        "vdr<msdv",
        ">     >v",
    )
    for row_offset, row in enumerate(scan_rows):
        for column_offset, character in enumerate(row):
            if character != " ":
                program.put(13 + column_offset, 7 + row_offset, character)
    program.put(20, 15, "<")
    program.put(6, 15, "v")

    # The next belt value is the target.  Swap it with the saved op and branch.
    program.put(6, 16, "W")
    program.put(6, 17, "X")

    # READ: restore the encoded cell, decode it, and send it to output.
    program.put(6, 18, ">")
    program.put(7, 18, "W")
    program.put(8, 18, "s")
    program.put(9, 18, "M")
    program.text(10, 18, f"`{VALUE_OFFSET}`")
    program.put(19, 18, "-")
    program.put(20, 18, "N")
    program.put(21, 18, "s")
    program.put(22, 18, "v")
    program.put(22, 19, "<")
    program.put(8, 19, "v")

    # WRITE: discard the old target, read and encode the replacement.
    program.put(5, 17, "v")
    program.put(5, 19, "<")
    program.put(2, 19, "v")
    program.put(2, 20, "r")
    program.put(2, 21, "M")
    program.put(2, 22, ">")
    program.text(3, 22, f"`{VALUE_OFFSET}`")
    program.put(12, 22, "+")
    program.put(13, 22, "v")
    program.put(13, 23, "<")
    program.put(9, 23, "s")
    program.put(8, 23, "v")

    # Finish the revolution. Encoded cells are positive; the sentinel is negative.
    program.put(8, 24, "v")
    program.put(8, 27, "<")
    program.put(6, 27, "^")
    program.put(6, 26, "^")
    program.put(6, 25, "r")
    program.put(6, 24, ">")
    program.put(7, 24, "v")
    program.put(7, 25, "s")
    program.put(7, 26, "X")
    program.put(24, 26, "^")
    program.put(24, 5, "<")


def _place_storage_belt(program: lm.Program, controller_bottom: int) -> None:
    """Create a square-packing FIFO ring with capacity above 101 values."""
    belt_left = 16
    belt_right = 33
    belt_top = controller_bottom + 8
    # Two rows leave enough pipe capacity for the 100 cells and sentinel.
    belt_rows = 2

    outbound = [(10, controller_bottom + 1), (10, belt_top), (belt_left, belt_top)]
    belt_y = belt_top
    going_right = True
    last_x = belt_left
    for _ in range(belt_rows):
        next_x = belt_right if going_right else belt_left
        outbound.append((next_x, belt_y))
        belt_y += 1
        outbound.append((next_x, belt_y))
        last_x = next_x
        going_right = not going_right
    if last_x != belt_right:
        outbound.append((belt_right, belt_y))
    outbound.append((belt_right + 1, belt_y))
    program.pipe(outbound)

    relay_x = belt_right + 2
    program.room(relay_x, belt_y - 2, 7, 5)
    program.text(relay_x + 1, belt_y - 1, "@>rsv")
    program.text(relay_x + 1, belt_y, ".^sr<")

    program.pipe([(relay_x - 1, belt_y + 1), (6, belt_y + 1), (6, controller_bottom + 1)])


def main() -> None:
    output = Path(__file__).with_name("simple-pipe.man")
    program = build_simple_pipe_memory()
    program.save(output)
    width, height, footprint = program.footprint()
    print(f"wrote {output} ({width}x{height}, footprint {footprint})")


if __name__ == "__main__":
    main()
