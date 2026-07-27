#!/usr/bin/env python3
"""Exhaustive semantic test for the merged base-64 dispatcher."""
from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scratchpad", "history-ring"))

from roomsim import run


WIDTH = 19
HEIGHT = 10
ESC = 29


def grid(*placements):
    cells = [[" "] * WIDTH for _ in range(HEIGHT)]
    for x, y, text in placements:
        for index, glyph in enumerate(text):
            assert cells[y][x + index] == " ", (x + index, y)
            cells[y][x + index] = glyph
    return tuple("".join(row) for row in cells)


ROWS = grid(
    # q=3: rem 0..7 is raw 84..91; rem 8/9 are raw/dict prefixes.
    (0, 0, "vs+W`511`M+a-W7M<"),
    # Initial splitter path and even quotient branch.
    (0, 1, "@v"), (12, 1, "<"), (13, 1, "vb"),
    (15, 1, "a"), (17, 1, "]<"),
    # Divide code by 18: A=quotient, B=remainder, then swap and branch.
    (1, 2, ">`18`Mr/bW       x"),
    # Odd quotient branch; q=1 descends at x=3, q=3 rises at x=16.
    (3, 3, "v"), (16, 3, "d]<"),
    # Prefixes: raw continues west; dictionary turns south at x=7.
    (0, 4, "^s+++++armb<"), (12, 4, "^     <"),
    # q=2 raw leaf. Dictionary tail crosses `b` at x=7.
    (1, 5, "^"), (6, 5, "sb+W`79`M<"), (18, 5, "s"),
    # q=1 raw leaf and selected dictionary output.
    (3, 6, ">M`65`W+s^"), (18, 6, "W"),
    # q=0 and dictionary joins; ring sentinel goes back out at x=18.
    (7, 7, "av    <"), (18, 7, "s"),
    # Canonical dictionary rotation/drain machinery.
    (8, 8, "> mdrMs>rX^"),
    (8, 9, "^sr<   ^s<"),
)


def make_pipe_for(ports):
    def pipe_for(x, y, kind):
        candidates = [(queue, attach) for queue, k, attach in ports if k == kind]
        return min(
            candidates,
            key=lambda item: (
                abs(item[1][0] - x) + abs(item[1][1] - y),
                item[1][1],
                item[1][0],
            ),
        )[0]

    return pipe_for


PORTS = (
    ("stream", "in", (-2, 4)),
    ("ring", "in", (14, 11)),
    ("unpack", "out", (18, -2)),
    ("ring", "out", (17, 11)),
)


def compact_protocol(symbols):
    codes = []
    index = 0
    while index < len(symbols):
        symbol = symbols[index]
        index += 1
        if symbol == ESC:
            position = symbols[index]
            index += 1
            if position == 17:
                codes.append(17)
            else:
                codes.extend((63, position))
        elif symbol <= 16:
            codes.append(symbol)
        elif 35 <= symbol <= 52:
            codes.append(symbol - 17)
        elif 66 <= symbol <= 91:
            codes.append(symbol - 30)
        else:
            codes.extend((62, symbol - 4))
    return codes


def main():
    rnd = random.Random(20260726)
    protocol = list(range(1, 18))
    expected = [1000 + value for value in protocol]
    for position in range(18, 53):
        protocol.extend((ESC, position))
        expected.append(1000 + position)
    raw_values = [
        value
        for value in range(18, 92)
        if value not in (ESC,)
    ]
    protocol.extend(raw_values)
    expected.extend(value + 31 for value in raw_values)
    for _ in range(500):
        if rnd.random() < 0.45:
            position = rnd.randint(1, 52)
            if position <= 17:
                protocol.append(position)
            else:
                protocol.extend((ESC, position))
            expected.append(1000 + position)
        else:
            value = rnd.choice(raw_values)
            protocol.append(value)
            expected.append(value + 31)

    ring0 = list(range(1001, 1053)) + [0]
    queues = {
        "stream": compact_protocol(protocol),
        "ring": list(ring0),
        "unpack": [],
    }
    result = run(
        list(ROWS),
        (0, 1),
        "E",
        queues,
        make_pipe_for(PORTS),
        max_steps=8_000_000,
    )
    if result["reason"] != "starved":
        raise AssertionError(result)
    if queues["unpack"] != expected:
        mismatch = next(
            index
            for index, pair in enumerate(
                zip(queues["unpack"] + [None], expected + [None])
            )
            if pair[0] != pair[1]
        )
        raise AssertionError(
            (
                mismatch,
                queues["unpack"][mismatch:mismatch + 8],
                expected[mismatch:mismatch + 8],
            )
        )
    assert queues["ring"] == ring0
    print(
        f"ok combined dispatcher {WIDTH}x{HEIGHT}: "
        f"{len(expected)} values, {result['steps']} room steps"
    )


if __name__ == "__main__":
    main()
