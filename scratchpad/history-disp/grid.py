#!/usr/bin/env python3
"""Index-addressed grid construction, so a miscounted run of spaces cannot
silently shift a glyph (it bit once already)."""


def rows(width, height, *placements):
    """placements: (x, y, text) tuples."""
    grid = [[" "] * width for _ in range(height)]
    for x, y, text in placements:
        for i, ch in enumerate(text):
            assert grid[y][x + i] == " ", (x + i, y, ch, grid[y][x + i])
            grid[y][x + i] = ch
    return ["".join(r) for r in grid]
