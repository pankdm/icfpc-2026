#!/usr/bin/env python3
"""Verify initial frames and parsed endpoints for every public LLM case."""
import json
import os
import sys

import build_pipes as build
import build_multi as multi
from verify_subset import expected_frames, run_flow


ROOT = os.path.abspath(os.path.join(build.HERE, "..", ".."))
sys.path.insert(0, ROOT)
from interpreter.parser import parse_program


def source_from_round(round_data):
    values = round_data["in"]
    width, height = int(values[0]), int(values[1])
    chars = [chr(int(value)) for value in values[2:]]
    return "\n".join(
        "".join(chars[y * width:(y + 1) * width])
        for y in range(height)
    )


def main():
    path = os.path.join(ROOT, "tests", "little-little-man.json")
    with open(path) as stream:
        spec = json.load(stream)
    total_pipes = total_ops = 0
    for case in spec["publicTestData"]:
        rounds = case["rounds"][:1]
        frames, ops, ram = run_flow(
            rounds, limit=5_000_000, builder=build, return_ram=True
        )
        assert frames == expected_frames(rounds), case["name"]
        source = source_from_round(rounds[0])
        source_rows = source.splitlines()
        top_offset = next(
            (index for index, row in enumerate(source_rows) if row.strip()), 0
        )
        nonblank = [row for row in source_rows if row.strip()]
        left_offset = min(len(row) - len(row.lstrip()) for row in nonblank)
        program = parse_program(source)
        expected_endpoints = {
            ((pipe.cells[-1][1] + top_offset) * 16
             + pipe.cells[-1][0] + left_offset,
             (pipe.cells[0][1] + top_offset) * 16
             + pipe.cells[0][0] + left_offset,
             pipe.destination_room + 1,
             pipe.source_room + 1)
            for pipe in program.pipes
        }
        count = ram[31]
        descriptors = ram[multi.DESC0:multi.DESC0 + count]
        got_endpoints = {
            (value & 255, (value >> 8) & 255,
             (value >> 16) & 7, (value >> 19) & 7)
            for value in descriptors
        }
        assert count == len(program.pipes), case["name"]
        assert got_endpoints == expected_endpoints, case["name"]
        total_pipes += count
        total_ops += ops
        print(f"PASS {case['name']}: initial frame, {count} pipe(s), {ops} Flow ops")

    # Seed a value into hello-neighbor's source immediately after its judged
    # initial frame. One target tick must move it exactly one cell toward the
    # destination and update both affected display pixels.
    transport_case = next(
        case for case in spec["publicTestData"] if case["name"] == "hello neighbor"
    )
    chain = []

    def seed_after_initial(frame_count, ram, next_pixels):
        if frame_count != 1:
            return
        descriptor = ram[multi.DESC0]
        current = descriptor & 255
        while True:
            chain.append(current)
            record = ram[multi.CELL0 + current]
            predecessor_code = (record >> 11) & 511
            if predecessor_code == 0:
                break
            current = predecessor_code - 1
        source = chain[-1]
        value_code = 15  # target value +5 is stored as code value+10.
        ram[multi.CELL0 + source] += (value_code << 20) + 8
        next_pixels[source] = 14

    frames, _ops, ram = run_flow(
        transport_case["rounds"][:2],
        limit=5_000_000,
        builder=build,
        frame_hook=seed_after_initial,
        return_ram=True,
    )
    assert len(chain) == 3
    assert [((ram[multi.CELL0 + addr] >> 20) & 31) for addr in chain] == [0, 15, 0]
    assert [frames[-1][addr] for addr in chain] == [6, 14, 6]
    print("PASS pipe transport: seeded value advanced one cell with exact deltas")

    print(f"PASS pipe topology: {len(spec['publicTestData'])} cases, "
          f"{total_pipes} parsed pipes, {total_ops} Flow ops")


if __name__ == "__main__":
    main()
