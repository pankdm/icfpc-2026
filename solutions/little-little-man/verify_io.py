#!/usr/bin/env python3
"""Exact-frame semantic regression for the target pipe-I/O candidate."""
import json
import os

import build_io as build
from verify_subset import expected_frames, run_flow


def main():
    path = os.path.join(build.HERE, "..", "..", "tests", "little-little-man.json")
    with open(path) as stream:
        spec = json.load(stream)
    passed = frames = ops_total = 0
    for case in spec["publicTestData"]:
        got, ops = run_flow(
            case["rounds"], limit=10_000_000, builder=build
        )
        expected = expected_frames(case["rounds"])
        if got != expected:
            mismatch = next(
                index for index, pair in enumerate(zip(got, expected))
                if pair[0] != pair[1]
            )
            raise AssertionError(f"{case['name']}: frame {mismatch + 1} differs")
        passed += 1
        frames += len(got)
        ops_total += ops
        print(f"PASS {case['name']}: {len(got)} frames, {ops} Flow ops")
    print(f"PASS pipe I/O: {passed}/{len(spec['publicTestData'])} cases, "
          f"{frames} frames, {ops_total} Flow ops")


if __name__ == "__main__":
    main()
