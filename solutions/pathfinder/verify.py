#!/usr/bin/env python3
"""Reference-model and Flow checks for Pathfinder."""

from collections import deque
import json
import os
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "solutions", "little-little-man"))

import build
from verify_subset import run_flow


DELTAS = (-16, 1, 16, -1)


def expected(rounds):
    return [
        [int(char, 16) for row in frame for char in row]
        for rnd in rounds for frame in rnd["frames"]
    ]


def reference(rounds):
    setup = list(map(int, rounds[0]["in"]))
    walls = setup[:256]
    robot = 16 * setup[257] + setup[256]
    pixels = [7 if wall else 0 for wall in walls]
    pixels[robot] = 10
    frames = [pixels.copy()]
    for rnd in rounds[1:]:
        fx, fy = map(int, rnd["in"])
        flag = 16 * fy + fx
        pixels[flag] = 9
        distance = {flag: 0}
        queue = deque([flag])
        while robot not in distance:
            cell = queue.popleft()
            for delta in DELTAS:
                neighbor = cell + delta
                if not walls[neighbor] and neighbor not in distance:
                    distance[neighbor] = distance[cell] + 1
                    queue.append(neighbor)
        while robot != flag:
            target = distance[robot] - 1
            move = next(
                neighbor for neighbor in (robot + d for d in DELTAS)
                if distance.get(neighbor) == target
            )
            pixels[robot] = 0
            robot = move
            pixels[robot] = 10
            frames.append(pixels.copy())
    return frames


def main():
    with open(os.path.join(ROOT, "tests", "pathfinder.json")) as stream:
        spec = json.load(stream)
    total = 0
    for case in spec["publicTestData"]:
        want = expected(case["rounds"])
        ref = reference(case["rounds"])
        assert ref == want, f"reference mismatch: {case['name']}"
        got, ops = run_flow(
            case["rounds"],
            builder=build,
            limit=15_000_000,
            expected_frames=len(want),
        )
        assert got == want, f"Flow mismatch: {case['name']}"
        total += ops
        print(f"PASS {case['name']}: {len(want)} frames, {ops} Flow ops")
    print(
        f"PASS Pathfinder reference + Flow: "
        f"{len(spec['publicTestData'])} cases, {total} ops"
    )


if __name__ == "__main__":
    main()

