#!/usr/bin/env python3
"""Verify a four-word parallel wavefront Pathfinder against public frames.

This models the intended hardware representation: four 64-bit words for the
current frontier and four for still-unvisited open cells.  Parent directions
are accumulated as four 256-bit masks in U/R/D/L priority order.
"""

import json
import os

from verify import expected


DELTAS = (-16, 1, 16, -1)
WORD_MASK = (1 << 64) - 1
ROW_MASK = (1 << 16) - 1
COL0 = sum(1 << (16 * row) for row in range(4))
COL15 = COL0 << 15


def words(bits):
    return [(bits >> (64 * i)) & WORD_MASK for i in range(4)]


def bits(ws):
    return sum(word << (64 * i) for i, word in enumerate(ws))


def expand(frontier, unvisited, parents):
    """One parallel BFS layer, assigning parents in U/R/D/L order."""
    f = words(frontier)
    u = words(unvisited)
    nxt = [0] * 4

    for direction in range(4):
        contribution = [0] * 4
        for i, word in enumerate(f):
            if direction == 0:  # cell moves U to reach previous frontier
                contribution[i] |= (word << 16) & WORD_MASK
                if i + 1 < 4:
                    contribution[i + 1] |= word >> 48
            elif direction == 1:  # R
                contribution[i] |= (word >> 1) & ~COL15
            elif direction == 2:  # D
                contribution[i] |= word >> 16
                if i:
                    contribution[i - 1] |= (word & ROW_MASK) << 48
            else:  # L
                contribution[i] |= (word << 1) & ~COL0 & WORD_MASK

        chosen = 0
        for i in range(4):
            take = contribution[i] & u[i]
            u[i] ^= take
            nxt[i] |= take
            chosen |= take << (64 * i)
        parents[direction] |= chosen

    return bits(nxt), bits(u)


def solve(rounds):
    setup = list(map(int, rounds[0]["in"]))
    walls = setup[:256]
    robot = 16 * setup[257] + setup[256]
    open_bits = sum((not wall) << i for i, wall in enumerate(walls))
    pixels = [7 if wall else 0 for wall in walls]
    pixels[robot] = 10
    frames = [pixels.copy()]

    for rnd in rounds[1:]:
        fx, fy = map(int, rnd["in"])
        flag = 16 * fy + fx
        pixels[flag] = 9
        frontier = 1 << flag
        unvisited = open_bits ^ frontier
        parents = [0, 0, 0, 0]
        while not (frontier >> robot) & 1:
            frontier, unvisited = expand(frontier, unvisited, parents)
            assert frontier, "no path"

        while robot != flag:
            bit = 1 << robot
            direction = next(i for i, mask in enumerate(parents) if mask & bit)
            pixels[robot] = 0
            robot += DELTAS[direction]
            pixels[robot] = 10
            frames.append(pixels.copy())
    return frames


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    with open(os.path.join(root, "tests", "pathfinder.json")) as stream:
        spec = json.load(stream)
    for case in spec["publicTestData"]:
        got = solve(case["rounds"])
        want = expected(case["rounds"])
        assert got == want, case["name"]
        print(f"PASS {case['name']}: {len(got)} frames")


if __name__ == "__main__":
    main()
