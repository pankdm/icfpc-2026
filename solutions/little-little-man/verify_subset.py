#!/usr/bin/env python3
"""Fast semantic verifier for build_subset.py's emitted Flow program.

The WASM editor oracle records a full world snapshot while stepping and exhausts
memory around 18M ticks for this deliberately large candidate.  This interpreter
executes the exact Flow token graph before geometry is applied, allowing complete
round/frame regression.  Short prefixes and load validity are still checked with
the WASM oracle.
"""
from collections import deque
import json
import os

import build_subset as build


MASK = (1 << 64) - 1


def s64(value):
    value &= MASK
    return value - (1 << 64) if value >= (1 << 63) else value


def run_flow(
    rounds,
    limit=2_000_000,
    builder=build,
    return_ram=False,
    frame_hook=None,
):
    blocks = builder.build_flow().blocks
    input_values = deque(int(value) for rnd in rounds for value in rnd["in"])
    ram = [0] * builder.RAM_N
    ram_cmd = []
    ram_replies = deque()
    scratch = deque()
    frames = []
    next_pixels = [0] * 256
    display_cursor = 0
    a = b = 0
    label = "START"
    pc = 0

    for steps in range(1, limit + 1):
        if pc >= len(blocks[label]):
            raise AssertionError(
                f"fell off end of Flow block {label!r} at step {steps}"
            )
        token = blocks[label][pc]
        pc += 1

        if isinstance(token, tuple):
            if token[0] == "go":
                label = token[1]
            else:
                _, positive, zero, negative = token
                label = positive if a > 0 else zero if a == 0 else negative
            pc = 0
            continue

        if token.isdigit():
            a = int(token)
        elif token == "M":
            b = a
        elif token == "W":
            a, b = b, a
        elif token == "+":
            a = s64(a + b)
        elif token == "-":
            a = s64(a - b)
        elif token == "*":
            a = s64(a * b)
        elif token == "N":
            a = s64(-a)
        elif token == "&":
            a = s64(a & b)
        elif token == "{":
            a = s64(a << b) if 0 <= b <= 63 else 0
        elif token == "}":
            a = 0 if b < 0 else (-1 if a < 0 else 0) if b > 63 else a >> b
        elif token == "/":
            if b == 0:
                a, b = 0, a
            else:
                quotient = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    quotient = -quotient
                a, b = quotient, a - quotient * b
        elif token == "ri":
            a = input_values.popleft()
        elif token == "sp":
            scratch.append(a)
        elif token == "rp":
            a = scratch.popleft()
        elif token == "sc":
            ram_cmd.append(a)
            if len(ram_cmd) >= 2:
                op, addr = ram_cmd[:2]
                if op == 0:
                    if not 0 <= addr < len(ram):
                        raise AssertionError(
                            f"RAM read address {addr} out of range at "
                            f"{label}[{pc - 1}], step {steps}"
                        )
                    ram_replies.append(ram[addr])
                    ram_cmd.clear()
                elif len(ram_cmd) == 3:
                    if not 0 <= addr < len(ram):
                        raise AssertionError(
                            f"RAM write address {addr} out of range at "
                            f"{label}[{pc - 1}], step {steps}; command={ram_cmd}"
                        )
                    ram[addr] = ram_cmd[2]
                    ram_cmd.clear()
        elif token == "rr":
            a = ram_replies.popleft()
        elif token == "sd":
            if not 0 <= a <= 15:
                raise AssertionError(f"display color {a} out of range")
            next_pixels[display_cursor] = a
            display_cursor = (display_cursor + 1) % 256
        elif token == "sa":
            if not 0 <= a < 256:
                raise AssertionError(f"display address {a} out of range")
            display_cursor = a
        elif token == "ss":
            frames.append(next_pixels.copy())
            if a == 0:
                next_pixels = [0] * 256
                display_cursor = 0
            elif a != 1:
                raise AssertionError(f"display swap value {a} is not 0 or 1")
            if frame_hook is not None:
                frame_hook(len(frames), ram, next_pixels)
            if len(frames) == len(rounds):
                if return_ram:
                    return frames, steps, ram
                return frames, steps
        else:
            raise AssertionError(f"unknown token {token!r}")

    raise AssertionError(f"Flow did not finish {len(rounds)} frames in {limit} ops")


def expected_frames(rounds):
    return [
        [int(char, 16) for row in rnd["frames"][0] for char in row]
        for rnd in rounds
    ]


def main():
    spec_path = os.path.join(build.HERE, "..", "..", "tests", "little-little-man.json")
    with open(spec_path) as stream:
        spec = json.load(stream)
    case = next(case for case in spec["publicTestData"] if case["name"] == "first steps")
    got, ops = run_flow(case["rounds"])
    expected = expected_frames(case["rounds"])
    assert got == expected
    print(f"PASS first steps: {len(got)}/{len(expected)} exact frames, {ops} Flow ops")


if __name__ == "__main__":
    main()
