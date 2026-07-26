#!/usr/bin/env python3
"""Exact public Flow verification for batched-read Pathfinder."""

import json
import os
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "solutions", "little-little-man"))

import build_async
from verify import expected
from verify_subset import run_flow


with open(os.path.join(ROOT, "tests", "pathfinder.json")) as stream:
    spec = json.load(stream)
for case in spec["publicTestData"]:
    want = expected(case["rounds"])
    got, ops = run_flow(
        case["rounds"],
        builder=build_async,
        limit=15_000_000,
        expected_frames=len(want),
    )
    assert got == want, case["name"]
    print(f"PASS {case['name']}: {len(want)} frames, {ops} Flow ops")
