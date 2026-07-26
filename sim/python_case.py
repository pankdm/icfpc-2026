#!/usr/bin/env python3
"""Run one cached display case without the WASM editor's snapshot recorder.

The official WASM editor is the final semantic oracle, but its recorder retains
enough history to exhaust the 4 GiB WebAssembly heap on long runs.  This runner
uses the dependency-free Python interpreter and releases each input round after
the preceding display frame commits, matching display-problem round gating.

Usage:
  python3 sim/python_case.py SLUG PROGRAM.man CASE [ROUND_COUNT] [--cap N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from interpreter.machine import LittlemanMachine, RuntimeFailure  # noqa: E402
from interpreter.parser import parse_program  # noqa: E402


def flatten_frame(rows: list[str]) -> tuple[int, ...]:
    return tuple(int(pixel, 16) for row in rows for pixel in row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("program", type=Path)
    parser.add_argument("case")
    parser.add_argument("round_count", type=int, nargs="?")
    parser.add_argument("--cap", type=int)
    parser.add_argument("--progress", type=int, default=500_000)
    args = parser.parse_args()

    spec = json.loads((REPO / "tests" / f"{args.slug}.json").read_text())
    case = next(
        (candidate for candidate in spec["publicTestData"] if candidate["name"] == args.case),
        None,
    )
    if case is None:
        parser.error(f"unknown case {args.case!r}")
    rounds = case["rounds"][: args.round_count]
    if not rounds:
        parser.error("round count must be positive")

    inputs = [[int(value) for value in round_["in"]] for round_ in rounds]
    expected = [
        flatten_frame(frame)
        for round_ in rounds
        for frame in round_.get("frames", [])
    ]
    if len(expected) != len(rounds):
        parser.error("runner currently requires exactly one expected frame per round")

    program = parse_program(args.program.read_text())
    cap = args.cap if args.cap is not None else spec.get("tickCap", 50_000_000)
    machine = LittlemanMachine(program, input_rounds=[inputs[0]], tick_limit=cap)
    next_report = args.progress
    matched = 0

    while machine.ticks < cap and matched < len(expected):
        machine.ticks += 1
        try:
            machine._tick()
        except RuntimeFailure as error:
            print(json.dumps({
                "status": "error",
                "ticks": machine.ticks,
                "matched": matched,
                "error": str(error),
            }))
            return 1

        while machine.display is not None and matched < len(machine.display.frames):
            got = machine.display.frames[matched]
            if got != expected[matched]:
                differing = next(
                    index
                    for index, (actual, wanted) in enumerate(zip(got, expected[matched]))
                    if actual != wanted
                )
                print(json.dumps({
                    "status": "wrong-frame",
                    "ticks": machine.ticks,
                    "frame": matched + 1,
                    "pixel": differing,
                    "expected": expected[matched][differing],
                    "actual": got[differing],
                }))
                return 1
            matched += 1
            print(json.dumps({
                "event": "frame",
                "ticks": machine.ticks,
                "matched": matched,
                "total": len(expected),
            }), flush=True)
            if matched < len(inputs):
                machine.available_input.extend(inputs[matched])

        if args.progress and machine.ticks >= next_report:
            print(json.dumps({
                "event": "progress",
                "ticks": machine.ticks,
                "matched": matched,
                "total": len(expected),
            }), flush=True)
            next_report += args.progress

    status = "pass" if matched == len(expected) else "step-cap"
    print(json.dumps({
        "status": status,
        "ticks": machine.ticks,
        "matched": matched,
        "total": len(expected),
        "cap": cap,
    }))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
