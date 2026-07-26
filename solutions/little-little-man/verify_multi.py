#!/usr/bin/env python3
"""Exact-frame semantic regression for the multi-room/no-pipe variant."""
import json
import os

import build_multi as build
from verify_subset import expected_frames, run_flow


CASES = ("first steps", "pileup", "bounce house")


def main():
    path = os.path.join(build.HERE, "..", "..", "tests", "little-little-man.json")
    with open(path) as stream:
        spec = json.load(stream)
    by_name = {case["name"]: case for case in spec["publicTestData"]}
    total_frames = total_ops = 0
    for name in CASES:
        case = by_name[name]
        got, ops = run_flow(case["rounds"], limit=5_000_000, builder=build)
        expected = expected_frames(case["rounds"])
        assert got == expected, name
        total_frames += len(got)
        total_ops += ops
        print(f"PASS {name}: {len(got)}/{len(expected)} exact frames, {ops} Flow ops")
    print(f"PASS multi-room slice: {len(CASES)} cases, {total_frames} frames, "
          f"{total_ops} Flow ops")


if __name__ == "__main__":
    main()
