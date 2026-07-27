#!/usr/bin/env python3
"""Exhaustive room tests for the narrow three-row base decoders."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scratchpad", "history-ring"))

from roomsim import run


DECODER64_ROWS = (
    ">W/WsWXU",
    "^`46`M<<",
    "@r     ^",
)
UNPACK128_ROWS = (
    ">>W/WsWXU",
    "^`821`M<<",
    "@r      ^",
)


def run_room(rows, inputs):
    queues = {"input": list(inputs), "output": []}

    def pipe_for(_x, _y, kind):
        if kind == "in":
            return "input", (7, -2)
        return "output"

    result = run(
        list(rows),
        (0, 2),
        "E",
        queues,
        pipe_for,
        max_steps=1_000_000,
    )
    assert result["reason"] == "starved", result
    return queues["output"]


def packed(digits, base):
    value = 0
    for digit in reversed(digits):
        value = value * base + digit
    return value


def main():
    for base, rows in ((64, DECODER64_ROWS), (128, UNPACK128_ROWS)):
        for length in range(1, 10):
            digits = [
                ((length * 17 + index * 23) % (base - 1)) + 1
                for index in range(length)
            ]
            actual = run_room(rows, [packed(digits, base)])
            assert actual == digits, (base, length, actual, digits)
        values = list(range(1, min(base, 64)))
        assert run_room(rows, [packed(values, base)]) == values
        print(
            f"ok base-{base}: interior "
            f"{max(map(len, rows))}x{len(rows)}"
        )


if __name__ == "__main__":
    main()
