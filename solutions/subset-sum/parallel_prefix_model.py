#!/usr/bin/env python3
"""Executable model for high-prefix parallel exhaustive subset sum."""

from __future__ import annotations

import random

from mitm_reference import PUBLIC, EXPECT, output as reference_output


PREFIX_BITS = 6


def mask_sum(values: list[int], mask: int) -> int:
    return sum(value for bit, value in enumerate(reversed(values)) if mask >> bit & 1)


def solve(values: list[int], target: int, prefix_bits: int = PREFIX_BITS) -> list[int]:
    n = len(values)
    prefix_bits = min(prefix_bits, n)
    suffix_bits = n - prefix_bits
    suffix_bound = 1 << suffix_bits

    for prefix in range((1 << prefix_bits) - 1, -1, -1):
        adjusted_target = target - mask_sum(values[:prefix_bits], prefix)
        if adjusted_target < 0:
            continue

        prefix_base = prefix * suffix_bound
        if adjusted_target == 0 and prefix:
            return render(values, prefix_base)

        for suffix in range(suffix_bound - 1, -1, -1):
            if prefix_base == 0 and suffix == 0:
                continue
            if mask_sum(values[prefix_bits:], suffix) == adjusted_target:
                return render(values, prefix_base + suffix)

    return [0]


def render(values: list[int], mask: int) -> list[int]:
    n = len(values)
    selected = [value for index, value in enumerate(values) if mask >> (n - 1 - index) & 1]
    return [len(selected), *selected]


if __name__ == "__main__":
    for (values, target), expected in zip(PUBLIC, EXPECT):
        actual = solve(values, target)
        print("OK" if actual == expected else "FAIL", actual)

    random.seed(20260725)
    for trial in range(2_000):
        size = random.randint(6, 16)
        values = [random.randint(1, 40) for _ in range(size)]
        target = random.randint(0, sum(values) + 5)
        actual = solve(values, target)
        expected = reference_output(values, target)
        if actual != expected:
            raise AssertionError(
                f"trial {trial}: values={values}, target={target}, "
                f"actual={actual}, expected={expected}"
            )
    print("fuzz: 2000/2000")
