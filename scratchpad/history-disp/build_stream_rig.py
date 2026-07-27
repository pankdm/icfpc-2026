#!/usr/bin/env python3
"""Probe a regenerating dictionary stream instead of a stored pipe ring.

The dictionary man walks its literal row forever.  Before every lookup DISP
drains through the zero sentinel, then receives the requested 1-based entry.
This makes dictionary-pipe capacity irrelevant at the cost of extra ticks.
History Lesson is footprint-only, so that is a favourable trade if it enables
the seven-row service layout.
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from littleman import Program

NPOS = 25


def disp_rows():
    rows = [
        "v@<<s  <  <         <",
        ">`23`Mr bX^          ",
        " >`31`+^ -           ",
        "vX~`92`M+X>rX>rmd   ^",
        ">rb       ^ <^  <    ",
    ]
    assert all(len(row) == 21 for row in rows)
    return rows


def build():
    program = Program()
    dx, dy = 10, 8
    program.room(dx, dy, 23, 7)
    for y, row in enumerate(disp_rows()):
        for x, glyph in enumerate(row):
            if glyph != " ":
                program.put(dx + 1 + x, dy + 1 + y, glyph)

    # A one-row cyclic dictionary.  Each lap sends positions 1..NPOS and a
    # zero sentinel, then the two-cell riser returns to the first literal.
    px, py = 38, 18
    values = [1000 + position for position in range(1, NPOS + 1)] + [0]
    # The return riser lands on `>` one cell west of @, so every subsequent
    # lap re-enters the first literal without falling through the bottom wall.
    cells = [">", "@"]
    for value in values:
        cells.extend(("`", *str(value), "`", "s"))
    end = 1 + len(cells)
    program.room(px, py, end + 3, 4)
    for index, glyph in enumerate(cells):
        program.put(px + 1 + index, py + 2, glyph)
    program.put(px + end, py + 2, "^")
    program.put(px + end, py + 1, "<")
    # Return west on the upper row, then descend immediately before @.
    program.put(px + 1, py + 1, "v")

    program.input_room(0, 9)
    program.output_room(14, 1)
    program.pipe([(3, 10), (9, 10)], end_direction="E")
    program.pipe([(16, 7), (16, 4)], end_direction="N")
    # Short one-way dictionary stream: no return leg and no capacity floor.
    program.pipe(
        [(px + 2, 17), (px + 2, 16), (35, 16), (35, 13), (33, 13)],
        end_direction="W",
    )
    return program


def case(count=300, seed=79):
    randomizer = random.Random(seed)
    stream, expected = [], []

    def emit(value):
        stream.append(value)
        if value == 0:
            expected.append(0)
        elif value <= 22:
            expected.append(1000 + value)
        else:
            expected.append(value + 31)

    for value in (0, 1, 22, 24, 28, 30, 91):
        emit(value)
    stream.extend((29, 25))
    expected.append(1025)
    for _ in range(count):
        if randomizer.random() < 0.55:
            emit(randomizer.randint(1, 22))
        elif randomizer.random() < 0.2:
            position = randomizer.randint(23, NPOS)
            stream.extend((29, position))
            expected.append(1000 + position)
        else:
            emit(randomizer.choice(
                [0, *range(24, 29), *range(30, 92)]
            ))
    return stream, expected


if __name__ == "__main__":
    candidate = build()
    path = os.path.join(HERE, "stream_rig.man")
    candidate.save(path)
    stream, expected = case()
    cases = {"publicTestData": [{
        "input": [str(value) for value in stream],
        "expectedOutput": [str(value) for value in expected],
    }]}
    with open(os.path.join(HERE, "stream_rig_cases.json"), "w") as handle:
        json.dump(cases, handle)
    print(path, candidate.footprint(), len(stream), len(expected))
