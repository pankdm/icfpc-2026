#!/usr/bin/env python3
"""Report calibrated metrics for parallel subset-sum layouts."""

import math


MASKS = 1 << 20
HEIGHT = 170
WORKER_PITCH = 46
FIXED_WIDTH = 77
GRID_FIXED_WIDTH = 53
ROW_STRIDE = 88
ROW_TICKS = 100

# Calibrated with isolated no-match n=20 runs:
#   N=64:  6,982,947 ticks for 16,384 masks
#   N=128: 3,525,923 ticks for  8,192 masks
# Difference is exactly 422 ticks per additional mask.
FIXED_TICKS = 68_899
TICKS_PER_MASK = 422

HORIZONTAL_LEX_TICKS = {8: 34_083, 16: 19_699, 32: 13_997, 64: 13_929}

# Pre-compaction 64-worker folded machines, retained for comparison.
# Tuple: width, height, lex-pin ticks, generated n=10 no-solution ticks.
FOLDED_ACTUAL = {
    1: (3926, 192, 13_929, 13_445),
    2: (2008, 302, 10_217, 9_727),
    3: (1408, 412, 9_149, 8_653),
    4: (1048, 522, 8_599, 8_067),
    5: (868, 632, 8_355, 7_847),
    6: (748, 742, 8_263, 7_749),
    7: (688, 852, 8_293, 7_773),
    8: (568, 962, 8_231, 7_675),
}

FOLDED32_ACTUAL = {
    1: (2006, 192, 13_997, 13_669),
    2: (1048, 302, 12_265, 11_903),
    3: (748, 412, 11_779, 11_439),
    4: (568, 522, 11_565, 11_219),
    5: (508, 632, 11_595, 11_243),
    6: (448, 742, 11_625, 11_267),
    7: (388, 852, 11_655, 11_291),
    8: (328, 962, 11_711, 11_315),
}

# Selected compact folds. Public ticks are the first six public cases; the final
# n=20 public case is omitted because the local Python interpreter is very slow.
# Tuple: rows, width, height, public ticks.
LARGE_FOLDED_ACTUAL = {
    64: (6, 559, 610, (8346, 7864, 88490, 7766, 23062, 7816)),
    128: (8, 789, 786, (6962, 6560, 47322, 6464, 14320, 6555)),
    256: (12, 1065, 1138, (6962, 6610, 27178, 6516, 10604, 6606)),
}


def horizontal_metrics(workers):
    width = WORKER_PITCH * workers + FIXED_WIDTH
    ticks = (
        FIXED_TICKS
        + TICKS_PER_MASK * (MASKS // workers)
        + WORKER_PITCH * (workers - 1)
    )
    footprint = max(width, HEIGHT) ** 2
    return width, HEIGHT, footprint, ticks, footprint * ticks


def folded_metrics(workers, rows):
    columns = math.ceil(workers / rows)
    width = WORKER_PITCH * columns + GRID_FIXED_WIDTH
    height = HEIGHT + ROW_STRIDE * (rows - 1)
    ticks = (
        FIXED_TICKS
        + TICKS_PER_MASK * (MASKS // workers)
        + WORKER_PITCH * (workers - 1)
        + ROW_TICKS * (rows - 1)
    )
    footprint = max(width, height) ** 2
    return columns, width, height, footprint, ticks, footprint * ticks


def number(value):
    return f"{value:,}"


def main():
    print("Horizontal variants")
    print("N | width | height | footprint | lex ticks | worst ticks | worst footprint*ticks")
    for workers in (8, 16, 32, 64, 128, 256):
        width, height, footprint, ticks, score = horizontal_metrics(workers)
        lex_ticks = HORIZONTAL_LEX_TICKS.get(workers)
        print(
            " | ".join(
                [
                    str(workers),
                    number(width),
                    number(height),
                    number(footprint),
                    number(lex_ticks) if lex_ticks is not None else "not measured",
                    number(ticks),
                    number(score),
                ]
            )
        )

    print("\nSelected compact folds")
    print(
        "workers | rows | columns | width | height | footprint | public ticks (first six) "
        "| projected worst ticks | projected footprint*ticks"
    )
    for workers, (rows, width, height, public_ticks) in LARGE_FOLDED_ACTUAL.items():
        columns = math.ceil(workers / rows)
        footprint = max(width, height) ** 2
        ticks = folded_metrics(workers, rows)[4]
        score = footprint * ticks
        print(
            " | ".join(
                (
                    number(workers),
                    number(rows),
                    number(columns),
                    number(width),
                    number(height),
                    number(footprint),
                    ", ".join(map(number, public_ticks)),
                    number(ticks),
                    number(score),
                )
            )
        )

    print("\nPre-compaction 64-worker row search")
    print(
        "rows | columns | width | height | footprint | lex ticks | no-solution ticks "
        "| projected worst ticks | projected footprint*ticks"
    )
    reference_no_solution = FOLDED_ACTUAL[1][3]
    horizontal_worst = horizontal_metrics(64)[3]
    for rows in range(1, 9):
        columns = math.ceil(64 / rows)
        width, height, lex_ticks, no_solution_ticks = FOLDED_ACTUAL[rows]
        footprint = max(width, height) ** 2
        projected_worst = horizontal_worst + no_solution_ticks - reference_no_solution
        projected_score = footprint * projected_worst
        print(
            " | ".join(
                map(
                    number,
                    (
                        rows,
                        columns,
                        width,
                        height,
                        footprint,
                        lex_ticks,
                        no_solution_ticks,
                        projected_worst,
                        projected_score,
                    ),
                )
            )
        )

    print("\nPre-compaction 32-worker row search")
    print(
        "rows | columns | width | height | footprint | lex ticks | no-solution ticks "
        "| projected worst ticks | projected footprint*ticks"
    )
    reference_no_solution = FOLDED32_ACTUAL[1][3]
    horizontal_worst = horizontal_metrics(32)[3]
    for rows in range(1, 9):
        columns = math.ceil(32 / rows)
        width, height, lex_ticks, no_solution_ticks = FOLDED32_ACTUAL[rows]
        footprint = max(width, height) ** 2
        projected_worst = horizontal_worst + no_solution_ticks - reference_no_solution
        projected_score = footprint * projected_worst
        print(
            " | ".join(
                map(
                    number,
                    (
                        rows,
                        columns,
                        width,
                        height,
                        footprint,
                        lex_ticks,
                        no_solution_ticks,
                        projected_worst,
                        projected_score,
                    ),
                )
            )
        )


if __name__ == "__main__":
    main()
