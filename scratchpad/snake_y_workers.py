#!/usr/bin/env python3
"""Probe a 16-way Y-forked occupancy service for Snake.

One master forks sixteen workers.  Each clone inherits its creation index in
``A``, copies it to ``BP``, and traverses a four-bit H-tree to a unique 4x4
worker tile.  All workers then block on distinct ``r`` cells attached to one
dispatch pipe, so pipe arbitration delivers each 16-word command batch in
creation order.

Worker state is a 16-bit occupancy mask in ``B``:

* 0: no-op;
* positive mask: query, sending 1 iff that bit is occupied;
* negative mask: toggle that bit.

The probe's long input pipe delays and densifies raw words before they reach
the worker farm.  A useful manual test is two 16-word batches: toggle worker 3
bit 2, then query it.  The sole expected integer output is 1.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

from layout import Layout


R0 = 32
WV = (14, 7)
WH = (14, 7)
XV = (19, 21)
XH = 50
FORK_X = 15
FARM_W = 80
FARM_H = 75


def leaf_pos(slot):
    b0, b1, b2, b3 = ((slot >> bit) & 1 for bit in range(4))
    row = R0 + (WV[0] if b0 else -WV[0]) + (WV[1] if b1 else -WV[1])
    col = XH + (-WH[0] if b2 else WH[0]) + (-WH[1] if b3 else WH[1])
    return col, row + 3


def put_worker(layout, x, y):
    """Worker arrives at (x,y) heading south; tile occupies x-5..x+4."""
    # Initialize B=0, then block at the tile's private receive cell.
    layout.put(x, y, "0")
    layout.put(x, y + 1, "M")
    layout.put(x, y + 2, "v")
    layout.put(x + 1, y + 2, "r")

    # Return rail approaches r from the east, then v turns south into X.
    layout.put(x + 5, y + 2, "<")
    layout.put(x, y + 4, "X")

    # Negative command: east, negate to mask, toggle B, save new state.
    layout.put(x + 1, y + 4, "N")
    layout.put(x + 2, y + 4, "~")
    layout.put(x + 3, y + 4, "M")
    layout.put(x + 4, y + 4, "v")
    layout.put(x + 4, y + 9, ">")

    # Positive command: west, test mask & B.  Zero continues west to return;
    # a hit turns north, sends 1, then takes the same west return column.
    layout.put(x - 1, y + 4, "&")
    layout.put(x - 2, y + 4, "X")
    layout.put(x - 5, y + 4, "v")
    layout.put(x - 2, y + 3, "1")
    layout.put(x - 2, y + 2, "s")
    layout.put(x - 2, y + 1, "<")
    layout.put(x - 5, y + 1, "v")
    layout.put(x - 5, y + 9, ">")

    # Zero command and all completed branches merge on the bottom return rail.
    layout.put(x, y + 9, ">")
    layout.put(x + 5, y + 9, "^")


def put_forker(layout):
    # Master starts with A=0 (worker index), BP=16 (workers remaining).
    layout.put(1, R0, "@")
    # 1 doubled four times -> 16, copied to BP; reset A to worker index 0.
    for x, glyph in enumerate("1M+M+M+M+b0", 2):
        layout.put(x, R0, glyph)
    layout.put(FORK_X - 2, R0, ">")
    layout.put(FORK_X - 1, R0, ">")
    layout.put(FORK_X, R0, "Y")

    # Clone is born north of Y.  It turns east, copies index A to BP, and
    # enters the H-tree root heading east.
    layout.put(FORK_X, R0 - 2, ">")
    layout.put(FORK_X + 1, R0 - 2, "b")
    layout.put(XV[0] - 2, R0 - 2, "v")
    layout.put(XV[0] - 2, R0 - 1, ">")
    layout.put(XV[0] - 1, R0 - 1, "v")
    layout.put(XV[0] - 1, R0, ">")

    # Original/master is born south. Increment index, decrement remaining,
    # and loop from the west while BP>0; the zero case exits south and halts.
    layout.put(FORK_X, R0 + 1, "M")
    layout.put(FORK_X, R0 + 2, "1")
    layout.put(FORK_X, R0 + 3, "+")
    layout.put(FORK_X, R0 + 4, "m")
    layout.put(FORK_X, R0 + 5, "d")
    layout.put(FORK_X - 2, R0 + 5, "^")
    layout.put(FORK_X, R0 + 7, "H")


def put_tree(layout):
    def node_v(level, col, row):
        layout.put(col, row, "x")
        for bit in (1, 0):
            sign = 1 if bit else -1
            layout.put(col, row + sign, "]")
            corner = row + sign * WV[level]
            layout.put(col, corner, ">")
            if level == 0:
                node_v(1, XV[1], corner)
            else:
                start_h(corner)

    def start_h(row):
        layout.put(XH, row, "v")
        node_h(0, XH, row + 1)

    def node_h(level, col, row):
        layout.put(col, row, "x")
        for bit in (1, 0):
            sign = -1 if bit else 1
            if level == 0:
                layout.put(col + sign, row, "]")
            corner = col + sign * WH[level]
            layout.put(corner, row, "v")
            if level == 0:
                node_h(1, corner, row + 1)
            else:
                put_worker(layout, corner, row + 1)

    node_v(0, XV[0], R0)


def build():
    layout = Layout()
    layout.room(0, 0, FARM_W, FARM_H)
    put_forker(layout)
    put_tree(layout)

    # The probe's input pipe is also an initialization barrier.  Its long
    # serpentine fills densely from I and, only after every worker is parked,
    # releases one word per tick into the farm.
    layout.input_room(0, -20)
    layout.pipe([
        (1, -17),
        (1, -16),
        (78, -16),
        (78, -14),
        (1, -14),
        (1, -11),
        (78, -11),
        (78, -8),
        (1, -8),
        (1, -5),
        (78, -5),
        (78, -3),
        (9, -3),
        (9, -1),
    ])

    # Only one incoming and one outgoing farm pipe: all worker r/s cells bind
    # unambiguously to these attachments.
    layout.output_room(FARM_W + 2, 0)
    layout.pipe([(FARM_W, 1), (FARM_W + 1, 1)])
    return layout


if __name__ == "__main__":
    program = build()
    output = os.path.join(REPO, "scratchpad", "snake_y_workers.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
    print("leaves", {slot: leaf_pos(slot) for slot in range(16)})
