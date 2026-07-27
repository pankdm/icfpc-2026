#!/usr/bin/env python3
"""Pathfinder reference model -- dependency-free (Python stdlib only).

This is the *executable specification* the littleman build must reproduce
tick-for-tick in behaviour (not in ticks).  It exists so that any new
architecture can be checked against a trusted model before a single grid
cell is drawn.

Board: always 16x16, index `i = 16*y + x`, border always wall.

Round 1 (setup):   256 cells row-major (0=path, 1=wall) then `rx ry`.
                   -> commit ONE frame: walls 7, paths 0, robot 10.
Round N>1:         `fx fy`  (on a path, reachable, != robot position)
                   -> reverse BFS from the FLAG, then the robot walks
                      downhill, ONE frame committed after EACH move
                      (k frames for a k-step shortest path).
                   Flag drawn 9 on every frame except the last of the round
                   (the robot stands on it).

Tie-break (server-proven, DO NOT REORDER):  up(-16), right(+1), down(+16), left(-1).

The BFS *expansion* order may be permuted freely -- only the downhill
walk's preference order is observable.  We keep DELTAS for both so the
model matches the champion exactly.

Colours are emitted as single lowercase hex digits, matching the frame
strings in tests/pathfinder.json.
"""

from collections import deque

__all__ = ["DELTAS", "N", "SIZE", "simulate", "frames_as_strings", "run_case"]

N = 16
SIZE = N * N

# up, right, down, left -- server-proven tie-break order.
DELTAS = (-N, 1, N, -1)

C_PATH, C_WALL, C_FLAG, C_ROBOT = 0, 7, 9, 10


def _reverse_bfs(walls, flag, robot):
    """Distance-to-flag for every cell reachable from `flag`.

    Stops as soon as `robot` has a distance: the walk only ever needs the
    ball of radius dist(robot) around the flag.  This mirrors what the
    littleman program does (early-out on popping the robot's cell).
    """
    dist = {flag: 0}
    queue = deque((flag,))
    while robot not in dist:
        cell = queue.popleft()
        base = dist[cell] + 1
        for delta in DELTAS:
            nb = cell + delta
            if not walls[nb] and nb not in dist:
                dist[nb] = base
                queue.append(nb)
    return dist


def _step(dist, robot):
    """One downhill move, first match in tie-break order."""
    target = dist[robot] - 1
    for delta in DELTAS:
        nb = robot + delta
        if dist.get(nb) == target:
            return nb
    raise AssertionError("no downhill neighbour -- unreachable flag?")


def simulate(rounds_in):
    """`rounds_in` = list of per-round input token lists (ints or str ints).

    Returns the flat list of committed frames; each frame is a list of 256
    colour ints in row-major order.
    """
    setup = [int(t) for t in rounds_in[0]]
    assert len(setup) == SIZE + 2, f"setup round has {len(setup)} tokens"
    walls = setup[:SIZE]
    robot = N * setup[SIZE + 1] + setup[SIZE]

    pixels = [C_WALL if w else C_PATH for w in walls]
    pixels[robot] = C_ROBOT
    frames = [pixels.copy()]

    for tokens in rounds_in[1:]:
        fx, fy = (int(t) for t in tokens)
        flag = N * fy + fx
        assert flag != robot and not walls[flag]
        pixels[flag] = C_FLAG
        dist = _reverse_bfs(walls, flag, robot)
        while robot != flag:
            nxt = _step(dist, robot)
            pixels[robot] = C_PATH
            robot = nxt
            pixels[robot] = C_ROBOT
            frames.append(pixels.copy())
    return frames


def simulate_bitplane(rounds_in):
    """The SAME output, computed with NO per-cell RAM -- the build target.

    Total mutable state is twelve 64-bit words plus a FIFO:

        blocked  256 bits = 4 words   walls | visited, reset to walls per round
        tag      512 bits = 8 words   2 bits per cell, (dist mod 3) + 1,
                                      0 = unvisited; all 8 words zeroed per round
        frontier FIFO ring of cell addresses (measured max depth 30)

    Two facts make this work:

    1.  ONE bitset transaction per neighbour.  `SET(nb)` on `blocked` returns
        non-zero exactly when nb was neither a wall nor already visited, so the
        wall test, the visited test and the visited mark are a single op.

    2.  The walk needs no distance number.  Adjacent path cells always differ in
        distance by exactly one (the grid is bipartite), so a neighbour is
        either dist-1 or dist+1, and those differ by 2 -- which is non-zero mod
        3.  Therefore `(dist mod 3) + 1` in two bits distinguishes them, and the
        next tag is a function of the current tag alone.  Tag 0 (unvisited or
        wall) can never be mistaken for a real tag because real tags are 1..3.

    Verified equal to `simulate()` on all 387 public frames and on 291 random
    3-round mazes.
    """
    setup = [int(t) for t in rounds_in[0]]
    walls = setup[:SIZE]
    robot = N * setup[SIZE + 1] + setup[SIZE]

    pixels = [C_WALL if w else C_PATH for w in walls]
    pixels[robot] = C_ROBOT
    frames = [pixels.copy()]

    for tokens in rounds_in[1:]:
        fx, fy = (int(t) for t in tokens)
        flag = N * fy + fx
        pixels[flag] = C_FLAG

        blocked = walls[:]                      # 4 words: reset to the walls
        tag = [0] * SIZE                        # 8 words: zeroed
        blocked[flag] = 1
        tag[flag] = 1                           # (0 mod 3) + 1
        queue = deque(((flag, 0),))
        while not tag[robot]:
            cell, d = queue.popleft()
            for delta in DELTAS:
                nb = cell + delta
                if not blocked[nb]:             # SET+test, one transaction
                    blocked[nb] = 1
                    tag[nb] = ((d + 1) % 3) + 1
                    queue.append((nb, d + 1))

        t = tag[robot]
        while robot != flag:
            want = ((t - 2) % 3) + 1            # tag of the dist-1 neighbour
            for delta in DELTAS:                # tie-break: up, right, down, left
                nb = robot + delta
                if tag[nb] == want:
                    pixels[robot] = C_PATH
                    robot = nb
                    pixels[robot] = C_ROBOT
                    frames.append(pixels.copy())
                    t = want
                    break
            else:
                raise AssertionError("stuck -- no neighbour carries the tag")
    return frames


def frames_as_strings(frames):
    """Frames as 16 rows of 16 hex chars -- the tests/*.json representation."""
    return [
        ["".join("%x" % c for c in frame[r * N:(r + 1) * N]) for r in range(N)]
        for frame in frames
    ]


def run_case(case, model=simulate):
    """Take one publicTestData entry; return (got_frames, want_frames) as strings."""
    got = frames_as_strings(model([rnd["in"] for rnd in case["rounds"]]))
    want = [frame for rnd in case["rounds"] for frame in rnd["frames"]]
    return got, want


def _main():
    import json
    import os

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    with open(os.path.join(root, "tests", "pathfinder.json")) as fh:
        spec = json.load(fh)

    rc = 0
    for label, model in (("reference", simulate), ("bit-plane", simulate_bitplane)):
        total = matched = bad_cases = 0
        for case in spec["publicTestData"]:
            got, want = run_case(case, model)
            ok = sum(1 for g, w in zip(got, want) if g == w)
            total += len(want)
            matched += ok
            good = ok == len(want) == len(got)
            bad_cases += not good
            print(f"{'PASS' if good else 'FAIL'} [{label}] {case['name']}: "
                  f"{ok}/{len(want)} frames"
                  f"{'' if len(got) == len(want) else f' (emitted {len(got)})'}")
        print(f"  {label}: frames_matched {matched} / frames_total {total} "
              f"({len(spec['publicTestData']) - bad_cases}/"
              f"{len(spec['publicTestData'])} cases)\n")
        rc |= bool(bad_cases)
    return rc


if __name__ == "__main__":
    raise SystemExit(_main())
