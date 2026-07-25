#!/usr/bin/env python3
"""Reference model and rough cost model for a streamed MITM Littleman design.

The intended machine stores one right-half residual in each comparator. A small
left-half engine emits ``(mask, sum)`` pairs in descending mask order. Every
comparator checks each pair concurrently; a balanced priority tree forwards the
first match, preferring larger right masks when matches are simultaneous.
"""

from __future__ import annotations

import math
import random

from mitm_reference import PUBLIC, EXPECT, output as reference_output


RIGHT_BITS = 10


def subset_sum(values: list[int], mask: int) -> int:
    return sum(value for bit, value in enumerate(reversed(values)) if mask >> bit & 1)


def solve(values: list[int], target: int, right_bits: int = RIGHT_BITS) -> list[int]:
    size = len(values)
    right_bits = min(right_bits, size)
    left_bits = size - right_bits
    left_values = values[:left_bits]
    right_values = values[left_bits:]

    residuals = [
        target - subset_sum(right_values, right_mask)
        for right_mask in range((1 << right_bits) - 1, -1, -1)
    ]

    for left_mask in range((1 << left_bits) - 1, -1, -1):
        left_sum = subset_sum(left_values, left_mask)
        for offset, residual in enumerate(residuals):
            if left_sum != residual:
                continue
            right_mask = (1 << right_bits) - 1 - offset
            full_mask = (left_mask << right_bits) | right_mask
            selected = [
                value
                for index, value in enumerate(values)
                if full_mask >> (size - 1 - index) & 1
            ]
            return [len(selected), *selected]
    return [0]


def estimate(
    comparator_count: int = 1 << RIGHT_BITS,
    comparator_cells: int = 64,
    ticks_per_left_mask: int = 18,
    fixed_ticks: int = 1_500,
) -> tuple[int, int, int]:
    left_masks = 1 << (20 - RIGHT_BITS)
    infrastructure_cells = 12_000
    occupied_cells = comparator_count * comparator_cells + infrastructure_cells
    side = math.ceil(math.sqrt(occupied_cells))
    ticks = fixed_ticks + left_masks * ticks_per_left_mask
    return side, ticks, side * side * ticks


def main() -> None:
    for (values, target), expected in zip(PUBLIC, EXPECT):
        actual = solve(values, target)
        print("OK" if actual == expected else "FAIL", actual)

    random.seed(20260725)
    for trial in range(2_000):
        size = random.randint(10, 20)
        values = [random.randint(1, 100_000) for _ in range(size)]
        target = random.randint(101, max(101, sum(values)))
        actual = solve(values, target)
        expected = reference_output(values, target, min(RIGHT_BITS, size))
        if actual != expected:
            raise AssertionError(
                f"trial {trial}: values={values}, target={target}, "
                f"actual={actual}, expected={expected}"
            )
    print("fuzz: 2000/2000")

    print("\nProjected n=20 scores")
    for cells, mask_ticks in ((96, 22), (64, 18), (48, 14), (32, 10), (24, 10)):
        side, ticks, score = estimate(
            comparator_cells=cells, ticks_per_left_mask=mask_ticks
        )
        print(
            f"{cells:2} cells/comparator, {mask_ticks:2} ticks/mask: "
            f"side~{side}, ticks~{ticks:,}, score~{score:,}"
        )


if __name__ == "__main__":
    main()
