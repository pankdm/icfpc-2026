#!/usr/bin/env python3
"""Summarize LLM public cases by interpreter capability.

This turns the cached round data back into source and reuses the repository's
validated Python littleman parser.  It is intentionally independent of any
candidate, so it remains useful for planning new interpreter slices and for
checking assumptions about private-case-like fixtures.
"""
import argparse
import json
import os
import sys


HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from interpreter.parser import parse_program


def source_from_case(case):
    values = case["rounds"][0]["in"]
    width, height = int(values[0]), int(values[1])
    cells = [chr(int(value)) for value in values[2:]]
    assert len(cells) == width * height
    return "\n".join(
        "".join(cells[y * width:(y + 1) * width])
        for y in range(height)
    )


def summarize(case):
    program = parse_program(source_from_case(case))
    ordinary = [room for room in program.rooms if room.kind == "ordinary"]
    instructions = {
        char
        for room in ordinary
        for y in range(room.top + 1, room.bottom)
        for char in program.grid[y][room.left + 1:room.right]
        if char != " "
    }
    steps = [int(rnd["in"][0]) for rnd in case["rounds"][1:]]
    return {
        "name": case["name"],
        "size": f"{program.width}x{program.height}",
        "rooms": len(ordinary),
        "men": sum(room.man_start is not None for room in ordinary),
        "pipes": len(program.pipes),
        "max_pipe": max((len(pipe.cells) for pipe in program.pipes), default=0),
        "rounds": len(case["rounds"]),
        "requested_ticks": sum(steps),
        "max_step": max(steps, default=0),
        "ops": "".join(sorted(instructions)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    path = os.path.join(ROOT, "tests", "little-little-man.json")
    with open(path) as stream:
        spec = json.load(stream)
    rows = [summarize(case) for case in spec["publicTestData"]]
    if args.json:
        print(json.dumps(rows, indent=2))
        return

    fields = ["name", "size", "rooms", "men", "pipes", "max_pipe",
              "rounds", "requested_ticks", "max_step", "ops"]
    widths = {
        field: max(len(field), *(len(str(row[field])) for row in rows))
        for field in fields
    }
    print("  ".join(field.ljust(widths[field]) for field in fields))
    print("  ".join("-" * widths[field] for field in fields))
    for row in rows:
        print("  ".join(str(row[field]).ljust(widths[field]) for field in fields))


if __name__ == "__main__":
    main()
