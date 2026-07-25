#!/usr/bin/env python3
"""Build a correctness-first parallel subset-sum machine.

Worker j scans masks ((q - 1) << k) | j for q descending from 2^(n-k) to 1,
where k = log2(worker count). Together the workers cover every non-empty n-bit
mask exactly once. Each worker returns its largest matching mask; the collector
takes the maximum mask and reuses the established belt-based reconstruction pass.
"""

from pathlib import Path
import math
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import littleman as lm


WORKERS = int(os.environ.get("SS_WORKERS", "64"))
if WORKERS < 1 or WORKERS > 256 or WORKERS & (WORKERS - 1):
    raise ValueError("SS_WORKERS must be a power of two between 1 and 256")
PARTITION_BITS = int(math.log2(WORKERS))
PREFIX_MODE = os.environ.get("SS_PREFIX") == "1"
COMPACT_WORKER = os.environ.get("SS_COMPACT_WORKER") == "1"
WORKER_IDS = list(range(WORKERS - 1, -1, -1)) if PREFIX_MODE else list(range(WORKERS))
WORKER_GAP = 45
WORKER_X0 = 50
WORKER_Y = 6
COLLECTOR_Y = 60


class Builder:
    def __init__(self):
        self.program = lm.Program()
        self.placed = {}

    def cell(self, x, y, char):
        old = self.placed.get((x, y))
        if old is not None and old != char:
            raise ValueError(f"collision at {(x, y)}: {old!r} vs {char!r}")
        self.placed[(x, y)] = char
        self.program.put(x, y, char)

    def room(self, x, y, width, height, glyphs="+-|"):
        self.program.room(x, y, width, height, glyphs)
        for column in range(width):
            self.placed[(x + column, y)] = self.program.get(x + column, y)
            self.placed[(x + column, y + height - 1)] = self.program.get(
                x + column, y + height - 1
            )
        for row in range(height):
            self.placed[(x, y + row)] = self.program.get(x, y + row)
            self.placed[(x + width - 1, y + row)] = self.program.get(
                x + width - 1, y + row
            )

    def man(self, x, y):
        self.program.man(x, y)
        self.placed[(x, y)] = "@"


COMPACT64_MAIN = (
    "           @rM6W-b 0Mrv",
    "vsN1M+rM+rM+rM+rM+rM+r<",
    ">   rv                 ",
    "  vs <                 ",
    " >v                    ",
    "  r                    ",
    "  s                    ",
    " ^Xv                   ",
    "   m                   ",
    "^ <d             >    v",
    "   >        r-MrWXWMv  ",
    " >v s*`360`MWsWsW<  `  ",
    "  r                 0  ",
    "  s                 6  ",
    " ^XMv               3  ",
    " v  <<              `  ",
    " >rX  >               v",
    "   +                *  ",
    "   s                   ",
    "vrb<                   ",
    ">sMv                   ",
    " >vr                   ",
    ">]vs                   ",
    " Wv<                   ",
    " -r                   0",
    " Ws >^                s",
    " xXWX rMrr+         >sH",
    "^<  >^                 ",
)


def build_compact_prefix_worker(builder, base_x, worker_id, worker_y, collector_y):
    p = builder.program
    C = builder.cell
    extra_bits = PARTITION_BITS - 6
    if extra_bits < 0:
        raise ValueError("compact prefix worker requires at least 64 workers")
    width_delta = 4 * extra_bits
    room_width = 25 + width_delta
    interior_width = room_width - 2
    main_left = base_x + 4
    main_top = worker_y
    builder.room(main_left, main_top, room_width, 30)
    builder.room(base_x, main_top + 21, 4, 6)

    shift_thresholds = {
        0: 11,
        2: 4,
        3: 5,
        9: 17,
        10: 12,
        12: 20,
        13: 20,
        14: 20,
        15: 20,
        16: 22,
        17: 20,
        24: 22,
        25: 22,
        26: 20,
    }
    rows = []
    for row_index, source in enumerate(COMPACT64_MAIN):
        row = [" "] * interior_width
        threshold = shift_thresholds.get(row_index)
        for column_index, character in enumerate(source):
            if character == " ":
                continue
            if row_index == 11 and 4 <= column_index <= 16:
                target = column_index + min(width_delta, 4)
            elif row_index == 11 and column_index in (17, 20):
                target = column_index + width_delta
            else:
                target = (
                    column_index + width_delta
                    if threshold is not None and column_index >= threshold
                    else column_index
                )
            row[target] = character
        rows.append(row)

    rows[1] = [" "] * interior_width
    rows[1][0:4] = "vsN1"
    rows[1][-1] = "<"
    cursor = interior_width - 2
    for index in range(PARTITION_BITS):
        rows[1][cursor] = "r"
        if worker_id >> (PARTITION_BITS - 1 - index) & 1:
            rows[1][cursor - 1] = "+"
            rows[1][cursor - 2] = "M"
        cursor -= 3

    digits = f"{worker_id:03d}"
    rows[0][14 + width_delta] = str(PARTITION_BITS)
    literal_delta = min(width_delta, 4)
    rows[11][7 + literal_delta : 10 + literal_delta] = reversed(digits)
    rows[12][20 + width_delta] = digits[0]
    rows[13][20 + width_delta] = digits[1]
    rows[14][20 + width_delta] = digits[2]

    for row_index, row in enumerate(rows):
        for column_index, character in enumerate(row):
            if character != " ":
                C(main_left + 1 + column_index, main_top + 1 + row_index, character)

    builder.man(base_x + 1, main_top + 22)
    C(base_x + 2, main_top + 22, "v")
    C(base_x + 1, main_top + 23, ">")
    C(base_x + 2, main_top + 23, "v")
    C(base_x + 1, main_top + 24, "s")
    C(base_x + 2, main_top + 24, "r")
    C(base_x + 1, main_top + 25, "^")
    C(base_x + 2, main_top + 25, "<")

    p.pipe(
        [
            (main_left - 1, main_top + 8),
            (base_x, main_top + 8),
            (base_x, main_top + 20),
        ]
    )
    p.pipe(
        [
            (base_x + 1, main_top + 20),
            (base_x + 1, main_top + 9),
            (main_left - 1, main_top + 9),
        ]
    )

    main_right = main_left + room_width - 1
    candidate_x = main_right + 2
    p.pipe(
        [
            (main_right + 1, main_top + 28),
            (candidate_x, main_top + 28),
            (candidate_x, collector_y - 1),
        ]
    )
    return candidate_x


def build_broadcaster(builder, width, output_columns):
    p = builder.program
    C = builder.cell
    builder.room(0, 0, width, 4)
    p.input_room(-5, 0)
    p.pipe([(-2, 1), (-1, 1)])
    builder.man(3, 1)
    C(4, 1, "r")
    C(5, 1, "b")
    C(6, 1, "S")
    C(7, 1, "M")
    C(8, 1, "1")
    C(9, 1, "{")
    C(10, 1, "M")
    C(11, 1, str(PARTITION_BITS))
    C(12, 1, "W")
    C(13, 1, "}")
    if PREFIX_MODE:
        C(14, 1, "M")
        C(16, 1, "1")
        C(17, 1, "N")
        C(18, 1, "S")
        C(19, 1, ">")
        C(20, 1, "r")
        C(21, 1, "S")
        C(22, 1, "m")
        C(23, 1, "d")
        C(23, 2, "<")
        C(19, 2, "^")
        C(24, 1, "r")
        C(25, 1, "S")
        C(26, 1, "W")
        C(27, 1, "S")
        C(28, 1, "H")
    else:
        C(14, 1, "S")
        C(15, 1, "1")
        C(16, 1, "N")
        C(17, 1, "S")
        C(18, 1, ">")
        C(19, 1, "r")
        C(20, 1, "S")
        C(21, 1, "v")
        C(21, 2, "<")
        C(18, 2, "^")

    for column, end_y in output_columns:
        p.pipe([(column, 4), (column, end_y)])


def build_worker(
    builder,
    base_x,
    worker_id,
    worker_y=WORKER_Y,
    collector_y=COLLECTOR_Y,
):
    if PREFIX_MODE and COMPACT_WORKER:
        return build_compact_prefix_worker(
            builder, base_x, worker_id, worker_y, collector_y
        )

    p = builder.program
    C0 = builder.cell
    ox, oy = base_x, worker_y
    digits = f"{worker_id:03d}"

    compact_main = False

    def C(x, y, char):
        if compact_main:
            x -= 1
            if 6 <= y <= 13:
                y -= 2
            elif 15 <= y <= 16:
                y -= 3
            elif y >= 18:
                y -= 4
        C0(ox + x, oy + y, char)

    builder.room(ox + 10, oy, 37, 54)
    if PREFIX_MODE:
        builder.room(ox + 5, oy + 34, 4, 6)
        p.pipe([(ox + 9, oy + 26), (ox + 7, oy + 26), (ox + 7, oy + 33)])
        p.pipe([(ox + 6, oy + 33), (ox + 6, oy + 16), (ox + 9, oy + 16)])
        builder.man(ox + 6, oy + 35)
        C(7, 35, "v")
        C(6, 36, ">")
        C(7, 36, "v")
        C(6, 37, "s")
        C(7, 37, "r")
        C(6, 38, "^")
        C(7, 38, "<")
    else:
        builder.room(ox + 2, oy + 36, 7, 4)
        p.pipe([(ox + 9, oy + 26), (ox + 5, oy + 26), (ox + 5, oy + 35)])
        p.pipe([(ox + 4, oy + 35), (ox + 4, oy + 16), (ox + 9, oy + 16)])
        C(3, 37, ">")
        builder.man(ox + 4, oy + 37)
        C(5, 37, "R")
        C(6, 37, "s")
        C(7, 37, "v")
        C(7, 38, "<")
        C(3, 38, "^")

    compact_main = True
    builder.man(ox + 11, oy + 2)
    C(13, 2, ">")
    if PREFIX_MODE:
        C(34, 2, "r")
        C(35, 2, "M")
        C(36, 2, str(PARTITION_BITS))
        C(37, 2, "W")
        C(38, 2, "-")
        C(39, 2, "b")
        C(40, 2, "0")
        C(41, 2, "M")
        C(42, 2, "r")
        C(45, 2, "v")
        C(45, 3, "<")
        for index in range(PARTITION_BITS):
            x = 44 - 3 * index
            C(x, 3, "r")
            if worker_id >> (PARTITION_BITS - 1 - index) & 1:
                C(x - 1, 3, "+")
                C(x - 2, 3, "M")
        C(44 - 3 * PARTITION_BITS, 3, "1")
        C(43 - 3 * PARTITION_BITS, 3, "N")
        C(42 - 3 * PARTITION_BITS, 3, "s")
        turn_x = 40 - 3 * PARTITION_BITS
        C(turn_x, 3, "v")
        C(turn_x, 6, ">")
        C(12, 6, ">")
    else:
        C(34, 2, "r")
        C(35, 2, "b")
        C(36, 2, "r")
        C(37, 2, "M")
        C(38, 2, "r")
        C(39, 2, "v")
        C(39, 3, "<")
        C(15, 3, "s")
        C(12, 3, "v")
        C(12, 6, ">")

    C(34, 6, "r")
    C(35, 6, "v")
    C(35, 7, "<")
    C(15, 7, "s")
    C(14, 7, "v")
    C(14, 8, "v")
    C(14, 9, "r")
    C(14, 10, "s")
    C(14, 11, "X")
    C(13, 11, "^")
    C(13, 8, ">")
    C(15, 11, "v")
    C(15, 12, "m")
    C(15, 13, "d")
    C(14, 13, "<")
    C(12, 13, "^")

    C(15, 15, ">")
    C(34, 15, "r")
    if PREFIX_MODE:
        C(35, 15, "-")
        C(36, 15, "M")
        C(37, 15, "r")
        C(38, 15, "W")
        C(39, 15, "X")

        C(39, 13, ">")
        C(42, 13, "0")
        C(44, 13, "v")
        C(44, 56, ">")

        C(40, 15, "W")
        C(41, 15, "M")
        C(42, 15, "v")
        C(42, 16, "`")
        C(42, 18, digits[0])
        C(42, 19, digits[1])
        C(42, 20, digits[2])
        C(42, 21, "`")
        C(42, 22, "*")
        C(42, 56, ">")

        C(39, 16, "<")
        C(38, 16, "W")
        C(37, 16, "s")
        C(36, 16, "W")
        C(35, 16, "s")
        C(34, 16, "W")
        C(33, 16, "M")
        C(32, 16, "`")
        C(31, 16, digits[0])
        C(30, 16, digits[1])
        C(29, 16, digits[2])
        C(28, 16, "`")
        C(27, 16, "*")
        C(26, 16, "s")
        C(12, 16, "v")
    else:
        C(35, 15, "W")
        C(36, 15, "v")
        C(36, 16, "<")
        C(15, 16, "s")
        C(14, 16, "W")
        C(13, 16, "s")
        C(12, 16, "v")
    C(12, 18, ">")
    C(13, 18, "v")
    C(13, 19, ">")
    C(14, 19, "v")
    C(14, 20, "r")
    C(14, 21, "s")
    C(14, 22, "X")
    C(13, 22, "^")
    C(13, 19, ">")
    C(15, 22, "M")

    C(16, 22, "v")
    C(16, 24, "v")
    C(16, 25, "<")
    C(12, 25, "v")
    C(12, 26, ">")

    C(14, 26, "r")
    C(15, 26, "X")
    C(15, 27, "+")
    C(15, 28, "s")
    if PREFIX_MODE:
        C(15, 29, "b")
        C(15, 30, "r")
        C(15, 31, "s")
        C(15, 32, "M")
        C(15, 33, "r")
        C(15, 34, "s")
    else:
        C(15, 29, "M")
        C(15, 30, str(PARTITION_BITS))
        C(15, 31, "W")
        C(15, 32, "{")
        C(15, 33, "M")
        C(15, 34, "`")
        C(15, 35, digits[0])
        C(15, 36, digits[1])
        C(15, 37, digits[2])
        C(15, 38, "`")
        C(15, 39, "W")
        C(15, 40, "|")
        C(15, 41, "b")
        C(15, 42, "r")
        C(15, 43, "s")
        C(15, 44, "M")
    C(15, 45, "<")
    C(14, 45, "v")
    C(14, 46, "v")
    C(14, 47, "v")

    C(14, 50, "r")
    C(14, 51, "s")
    C(14, 52, "X")
    C(13, 52, "x")
    C(13, 51, "W")
    C(13, 50, "-")
    C(13, 49, "M")
    C(13, 48, "]")
    C(13, 47, ">")
    C(13, 53, "]")
    C(13, 54, "<")
    C(12, 54, "^")
    C(12, 46, ">")

    C(15, 52, "W")
    C(16, 52, "X")
    C(16, 53, ">")
    C(24, 53, "^")
    C(16, 51, ">")
    C(24, 51, "^")
    C(24, 24, "<")

    C(17, 52, ">")
    C(18, 52, "v")
    C(18, 55, ">")
    C(20, 55, "r")
    C(21, 55, "M")
    if PREFIX_MODE:
        C(22, 55, "r")
        C(23, 55, "r")
        C(24, 55, "+")
        C(25, 55, "v")
        C(25, 56, ">")
    else:
        C(22, 55, str(PARTITION_BITS))
        C(23, 55, "W")
        C(24, 55, "{")
        C(25, 55, "M")
        C(26, 55, "`")
        C(27, 55, digits[0])
        C(28, 55, digits[1])
        C(29, 55, digits[2])
        C(30, 55, "`")
        C(31, 55, "W")
        C(32, 55, "|")
        C(33, 55, "v")
        C(33, 56, ">")

    C(16, 26, "0")
    C(17, 26, ">")
    C(35, 26, "v")
    C(35, 56, ">")
    C(45, 56, "s")
    C(46, 56, "H")

    candidate_x = ox + 48
    p.pipe(
        [
            (ox + 47, oy + 52),
            (candidate_x, oy + 52),
            (candidate_x, collector_y - 1),
        ]
    )
    return candidate_x


def build_collector(builder, right, candidate_columns, collector_y=COLLECTOR_Y):
    p = builder.program
    C0 = builder.cell
    ox, oy = 0, collector_y

    compact_tail = False

    def C(x, y, char):
        if compact_tail and y >= 45:
            y -= 8
        C0(ox + x, oy + y, char)

    builder.room(10, oy, right - 10, 80)
    builder.room(2, oy + 32, 7, 5)
    p.pipe(
        [(9, oy + 77), (1, oy + 77), (1, oy + 38), (5, oy + 38), (5, oy + 37)]
    )
    p.pipe([(4, oy + 31), (4, oy + 20), (9, oy + 20)])
    C(3, 33, ">")
    builder.man(4, oy + 33)
    C(5, 33, "R")
    C(6, 33, "s")
    C(7, 33, "v")
    C(7, 34, "<")
    C(3, 34, "^")

    stream_x = right - 6

    builder.man(12, oy + 2)
    C(13, 2, ">")
    C(stream_x, 2, "r")
    C(stream_x + 1, 2, "b")
    C(stream_x + 2, 2, "r")
    if PREFIX_MODE:
        C(stream_x + 3, 2, "v")
        C(stream_x + 3, 3, "<")
    else:
        C(stream_x + 3, 2, "r")
        C(stream_x + 4, 2, "v")
        C(stream_x + 4, 3, "<")
    C(15, 3, "s")
    C(12, 3, "v")
    C(12, 6, ">")

    C(stream_x, 6, "r")
    C(stream_x + 1, 6, "^")
    C(stream_x + 1, 5, "<")
    C(15, 5, "v")
    C(15, 7, "s")
    C(15, 8, "<")
    C(14, 8, "v")
    C(14, 11, "v")
    C(14, 12, "r")
    C(14, 13, "s")
    C(14, 14, "X")
    C(13, 14, "^")
    C(13, 11, ">")
    C(15, 14, "v")
    C(15, 15, "m")
    C(15, 16, "d")
    C(14, 16, "<")
    C(12, 16, "^")

    C(15, 18, ">")
    C(stream_x, 18, "r")
    C(stream_x + 1, 18, "v")
    C(stream_x + 1, 19, "<")
    C(15, 19, "s")
    C(14, 19, "v")
    C(14, 22, "r")
    C(14, 23, "s")
    C(14, 24, "X")
    C(13, 24, "^")
    C(13, 21, ">")
    C(14, 21, "v")
    if not PREFIX_MODE:
        C(15, 24, "0")
        C(16, 24, "M")
    C(17, 24, "^")
    C(17, 8, ">")

    end_x = candidate_columns[-1] + 12
    if PREFIX_MODE:
        for column in candidate_columns:
            C(column, 8, "r")
            C(column + 1, 8, "X")
            C(column + 1, 9, ">")
        C(end_x, 8, "0")
        C(end_x + 1, 8, "v")
        C(end_x + 1, 9, "v")
    else:
        for column in candidate_columns:
            x = column
            C(x, 8, "r")
            C(x + 1, 8, "-")
            C(x + 2, 8, "X")
            C(x + 2, 7, ">")
            C(x + 7, 7, "v")
            C(x + 2, 9, "+")
            C(x + 2, 10, "M")
            C(x + 2, 11, ">")
            C(x + 7, 11, "^")
            C(x + 7, 8, ">")
        C(end_x, 8, "W")
        C(end_x + 1, 8, "v")
    C(end_x + 1, 14, "<")
    C(16, 14, "v")
    C(16, 26, "X")

    C(15, 26, "<")
    C(14, 26, "s")
    C(13, 26, "v")
    C(14, 27, "v")
    C(14, 28, "r")
    C(14, 29, "s")
    C(14, 30, "X")
    C(13, 30, "^")
    C(13, 27, ">")
    C(15, 30, "v")
    compact_tail = True
    C(15, 45, "<")
    C(14, 45, "v")

    C(16, 27, "v")
    C(16, 31, ">")
    C(60, 31, "v")
    C(60, 70, "<")
    C(45, 70, "s")
    C(44, 70, "H")

    C(14, 46, "r")
    C(14, 47, "b")
    C(14, 48, "s")
    C(14, 49, "1")
    C(14, 50, "M")
    C(14, 51, "0")
    C(14, 52, ">")
    C(26, 52, "d")
    C(26, 53, "x")
    C(25, 53, "+")
    C(24, 53, "v")
    C(27, 53, "v")
    C(24, 54, ">")
    C(26, 54, "v")
    C(27, 54, "<")
    C(26, 55, "]")
    C(26, 56, "<")
    C(23, 56, "^")
    C(23, 52, ">")
    C(27, 52, "M")
    C(45, 52, "s")
    C(46, 52, "v")
    C(46, 57, "<")
    C(14, 57, "v")
    C(14, 58, "r")
    C(14, 59, "s")
    C(14, 60, "X")
    C(13, 60, "^")
    C(13, 57, ">")
    C(15, 60, "v")
    C(15, 61, "<")
    C(14, 61, "v")

    C(14, 62, "r")
    C(14, 63, "b")
    C(14, 64, "r")
    C(14, 65, "v")
    C(14, 66, "v")
    C(14, 68, "r")
    C(14, 69, "X")
    C(13, 69, "x")
    C(13, 68, "s")
    C(13, 67, "]")
    C(13, 66, ">")
    C(13, 70, "]")
    C(13, 71, "<")
    C(12, 71, "^")
    C(12, 65, ">")
    C(15, 69, "v")
    C(15, 73, "<")
    C(14, 73, "v")

    C(14, 74, "W")
    C(14, 75, "X")
    C(14, 76, "H")
    C(13, 75, "v")
    C(13, 76, "b")
    C(13, 77, "M")
    C(13, 78, "1")
    C(13, 79, "W")
    C(13, 80, "-")
    C(13, 81, "M")
    C(13, 82, "v")
    C(13, 83, "r")
    C(13, 84, "m")
    C(13, 85, "a")
    C(14, 85, "s")
    C(15, 85, "^")
    C(15, 82, "<")
    C(13, 86, ">")
    C(45, 86, "s")
    C(46, 86, "^")
    C(46, 73, "<")

    p.output_room(44, oy + 82)
    p.pipe([(45, oy + 80), (45, oy + 81)])


def build():
    builder = Builder()
    worker_bases = [WORKER_X0 + index * WORKER_GAP for index in range(len(WORKER_IDS))]
    candidate_columns = [base + 48 for base in worker_bases]
    collector_right = candidate_columns[-1] + 24
    broadcast_outputs = [
        (base + 33, WORKER_Y - 1) for base in worker_bases
    ]
    build_broadcaster(builder, collector_right, broadcast_outputs)
    builder.program.pipe(
        [
            (collector_right, 2),
            (collector_right + 1, 2),
            (collector_right + 1, COLLECTOR_Y + 6),
            (collector_right, COLLECTOR_Y + 6),
        ]
    )
    built_candidates = [
        build_worker(builder, base, worker_id)
        for worker_id, base in zip(WORKER_IDS, worker_bases)
    ]
    build_collector(builder, collector_right, built_candidates)
    return builder.program


if __name__ == "__main__":
    program = build()
    suffix = "-prefix" if PREFIX_MODE else ""
    destination = Path(__file__).with_name(f"parallel{WORKERS}{suffix}.man")
    program.save(str(destination))
    print(program.render())
    print("footprint", program.footprint())
