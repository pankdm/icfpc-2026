#!/usr/bin/env python3
"""Reference-model checks for Snake public data and generated Flow."""

import json
import os
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "solutions", "little-little-man"))

import build
from verify_subset import run_flow


def reference(rounds):
    body = []
    direction = 3
    fruit = None
    alive = True
    pixels = [0] * 256
    frames = []
    for number, rnd in enumerate(rounds):
        values = list(map(int, rnd["in"]))
        if number == 0:
            x, y = values
            body = [16 * y + x]
            pixels[body[0]] = 10
            frames.append(pixels.copy())
            continue
        command = values[0]
        if command == 1:
            fruit = 16 * values[2] + values[1]
            pixels[fruit] = 9
            frames.append(pixels.copy())
        elif command in (2, 3, 4, 5):
            direction = command
        else:
            head = body[-1]
            x, y = head & 15, head >> 4
            nx, ny = ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))[direction - 2]
            new = 16 * ny + nx
            grow = new == fruit
            occupied = set(body if grow else body[1:])
            if not (0 <= nx < 16 and 0 <= ny < 16) or new in occupied:
                alive = False
                for cell in body:
                    pixels[cell] = 9
            else:
                if not grow:
                    pixels[body.pop(0)] = 0
                else:
                    fruit = None
                body.append(new)
                pixels[new] = 10
            frames.append(pixels.copy())
        if not alive:
            break
    return frames


def expected(rounds):
    return [
        [int(char, 16) for row in frame for char in row]
        for rnd in rounds for frame in rnd["frames"]
    ]


def main():
    with open(os.path.join(ROOT, "tests", "snake.json")) as stream:
        spec = json.load(stream)
    total = 0
    for case in spec["publicTestData"]:
        want = expected(case["rounds"])
        ref = reference(case["rounds"])
        assert ref == want, f"reference mismatch: {case['name']}"
        got, ops = run_flow(
            case["rounds"],
            builder=build,
            limit=5_000_000,
            expected_frames=len(want),
        )
        assert got == want, f"Flow mismatch: {case['name']}"
        total += ops
        print(f"PASS {case['name']}: {len(want)} frames, {ops} Flow ops")
    print(f"PASS Snake reference + Flow: {len(spec['publicTestData'])} cases, {total} ops")


if __name__ == "__main__":
    main()

