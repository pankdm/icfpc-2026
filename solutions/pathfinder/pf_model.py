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


def frames_as_strings(frames):
    """Frames as 16 rows of 16 hex chars -- the tests/*.json representation."""
    return [
        ["".join("%x" % c for c in frame[r * N:(r + 1) * N]) for r in range(N)]
        for frame in frames
    ]


def run_case(case):
    """Take one publicTestData entry; return (got_frames, want_frames) as strings."""
    got = frames_as_strings(simulate([rnd["in"] for rnd in case["rounds"]]))
    want = [frame for rnd in case["rounds"] for frame in rnd["frames"]]
    return got, want


def _main():
    import json
    import os

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    with open(os.path.join(root, "tests", "pathfinder.json")) as fh:
        spec = json.load(fh)

    total = matched = 0
    bad_cases = 0
    for case in spec["publicTestData"]:
        got, want = run_case(case)
        ok = sum(1 for g, w in zip(got, want) if g == w)
        total += len(want)
        matched += ok
        status = "PASS" if (ok == len(want) == len(got)) else "FAIL"
        if status == "FAIL":
            bad_cases += 1
        print(f"{status} {case['name']}: {ok}/{len(want)} frames"
              f"{'' if len(got) == len(want) else f' (emitted {len(got)})'}")
    print(f"\nframes_matched {matched} / frames_total {total} "
          f"({len(spec['publicTestData']) - bad_cases}/"
          f"{len(spec['publicTestData'])} cases)")
    return 0 if bad_cases == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())
