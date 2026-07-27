#!/usr/bin/env python3
"""Fast semantic verifier for the generated MEM16 Pathfinder control flow."""

from collections import deque
import json
import os

import build_mem16_flow as build
from pf_model import frames_as_strings


MASK64 = (1 << 64) - 1
KEEP_WALLS = 0x4444444444444444


def s64(value):
    value &= MASK64
    return value - (1 << 64) if value >= 1 << 63 else value


def run_flow(flow, rounds, limit=5_000_000):
    blocks = flow.blocks
    inputs = deque(int(v) for rnd in rounds for v in rnd["in"])
    state, frontier, nb = deque(), deque(), deque()
    memory = [0] * 16
    mem_cmd = []
    replies = deque()
    pixels = [0] * 256
    frames = []
    display_addr = None
    a = b = 0
    label, pc = "START", 0

    for steps in range(1, limit + 1):
        token = blocks[label][pc]
        pc += 1
        if isinstance(token, tuple):
            if token[0] == "go":
                label = token[1]
            else:
                label = token[1] if a > 0 else token[2] if a == 0 else token[3]
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
        elif token == "|":
            a = s64(a | b)
        elif token == "~":
            a = s64(a ^ b)
        elif token == "{":
            a = s64(a << b) if 0 <= b <= 63 else 0
        elif token == "}":
            a = 0 if b < 0 else (-1 if a < 0 else 0) if b > 63 else a >> b
        elif token == "%":
            a = 0 if b == 0 else a % b
        elif token == "/":
            if b == 0:
                a, b = 0, a
            else:
                q = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    q = -q
                a, b = q, a - q * b
        elif token == "Ir":
            a = inputs.popleft()
        elif token == "Ss":
            state.append(a)
        elif token == "Sr":
            a = state.popleft()
        elif token == "Fs":
            if a < 0:
                raise AssertionError(
                    f"negative frontier value {a} at {label}[{pc - 1}], "
                    f"step {steps}; state={list(state)}, B={b}, "
                    f"memory0={memory[0]:#x}"
                )
            frontier.append(a)
        elif token == "Fr":
            if not frontier:
                raise AssertionError(
                    f"empty frontier at {label}[{pc - 1}], step {steps}; "
                    f"state={list(state)}, memory={memory}"
                )
            a = frontier.popleft()
        elif token == "Ns":
            nb.append(a)
        elif token == "Nr":
            a = nb.popleft()
        elif token == "Hs":
            if not mem_cmd and a < 0:
                memory[:] = [word & KEEP_WALLS for word in memory]
            else:
                mem_cmd.append(a)
                if len(mem_cmd) == 2:
                    word, mask = mem_cmd
                    replies.append(memory[word] & mask)
                elif len(mem_cmd) == 3:
                    word, _mask, payload = mem_cmd
                    memory[word] |= payload
                    mem_cmd.clear()
        elif token == "Cr":
            if not replies:
                raise AssertionError(
                    f"empty memory reply at {label}[{pc - 1}], step {steps}; "
                    f"mem_cmd={mem_cmd}, A={a}, B={b}, state={list(state)}"
                )
            a = replies.popleft()
        elif token == "Ds":
            if a < 0:
                frames.append(pixels.copy())
                display_addr = None
            elif display_addr is None:
                display_addr = a
            else:
                pixels[display_addr] = a
                display_addr = None
        elif token == "H":
            break
        else:
            raise AssertionError(f"unknown token {token!r} at {label}[{pc - 1}]")

        wanted = sum(len(rnd["frames"]) for rnd in rounds)
        if len(frames) == wanted:
            return frames, steps
    raise AssertionError(
        f"flow did not finish: step={steps}, label={label}, pc={pc}, "
        f"state={list(state)}, nb={list(nb)}, frontier={len(frontier)}, "
        f"mem_cmd={mem_cmd}"
    )


def main():
    with open(os.path.join(build.REPO, "tests", "pathfinder.json")) as stream:
        cases = json.load(stream)["publicTestData"]
    for variant, make_flow in (
        ("two-ring", build.build_flow),
        ("one-ring", build.build_flow_one_ring),
    ):
        for case in cases:
            got, steps = run_flow(make_flow(), case["rounds"])
            want = [frame for rnd in case["rounds"] for frame in rnd["frames"]]
            got = frames_as_strings(got)
            assert got == want, (variant, case["name"])
            print(
                f"PASS {variant} {case['name']}: "
                f"{len(got)} frames, {steps} flow ops"
            )


if __name__ == "__main__":
    main()
