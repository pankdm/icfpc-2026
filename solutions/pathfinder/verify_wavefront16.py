#!/usr/bin/env python3
"""Execute build_wavefront16's exact Flow graph against public frames."""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, HERE)

import build_wavefront16 as build
from verify import expected


def load_flow_runner():
    path = os.path.join(ROOT, "solutions", "little-little-man", "verify_subset.py")
    spec = importlib.util.spec_from_file_location("flow_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_flow


def main():
    run_flow = load_flow_runner()
    with open(os.path.join(ROOT, "tests", "pathfinder.json")) as stream:
        spec = json.load(stream)
    for case in spec["publicTestData"]:
        want = expected(case["rounds"])
        got, ops = run_flow(
            case["rounds"],
            builder=build,
            expected_frames=len(want),
            limit=20_000_000,
        )
        assert got == want, case["name"]
        print(f"PASS {case['name']}: {len(got)} frames, {ops} Flow ops")


if __name__ == "__main__":
    main()
