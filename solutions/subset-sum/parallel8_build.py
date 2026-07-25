#!/usr/bin/env python3
"""Build a correctness-first 64-worker subset-sum machine.

Worker j scans masks ((q - 1) << 6) | j for q descending from 2^(n-6) to 1.
Together the workers cover every non-empty n-bit mask exactly once.  Each worker
returns its largest matching mask; the collector takes the maximum mask and
reuses the established belt-based reconstruction pass from ss.man.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import littleman as lm


WORKERS = 64
PARTITION_BITS = 6
WORKER_IDS = list(range(WORKERS))
WORKER_GAP = 60
WORKER_X0 = 50
WORKER_Y = 20
COLLECTOR_Y = 90


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


def build_broadcaster(builder, width, output_columns):
    p = builder.program
    C = builder.cell
    builder.room(0, 0, width, 7)
    p.input_room(3, -5)
    p.pipe([(4, -2), (4, -1)])
    builder.man(3, 2)
    C(4, 2, "r")
    C(5, 2, "S")
    C(6, 2, "v")
    C(6, 3, "<")
    C(2, 3, "^")
    C(2, 2, ">")

    for column, end_y in output_columns:
        p.pipe([(column, 7), (column, end_y)])


def build_worker(builder, base_x, worker_id):
    p = builder.program
    C0 = builder.cell
    ox, oy = base_x, WORKER_Y

    def C(x, y, char):
        C0(ox + x, oy + y, char)

    builder.room(ox + 10, oy, 42, 66)
    builder.room(ox + 2, oy + 40, 7, 5)
    p.pipe([(ox + 9, oy + 30), (ox + 5, oy + 30), (ox + 5, oy + 39)])
    p.pipe([(ox + 4, oy + 39), (ox + 4, oy + 20), (ox + 9, oy + 20)])
    C(3, 41, ">")
    builder.man(ox + 4, oy + 41)
    C(5, 41, "R")
    C(6, 41, "s")
    C(7, 41, "v")
    C(7, 42, "<")
    C(3, 42, "^")

    builder.man(ox + 12, oy + 2)
    C(13, 2, ">")
    C(34, 2, "r")
    C(35, 2, "b")
    C(36, 2, "M")
    C(37, 2, "1")
    C(38, 2, "{")
    C(39, 2, "M")
    C(40, 2, str(PARTITION_BITS))
    C(41, 2, "W")
    C(42, 2, "}")
    C(43, 2, "M")
    C(44, 2, "1")
    C(45, 2, "N")
    C(46, 2, "v")
    C(46, 3, "<")
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
    C(15, 29, "M")
    C(15, 30, str(PARTITION_BITS))
    C(15, 31, "W")
    C(15, 32, "{")
    C(15, 33, "M")
    digits = f"{worker_id:02d}"
    C(15, 34, "`")
    C(15, 35, digits[0])
    C(15, 36, digits[1])
    C(15, 37, "`")
    C(15, 38, "W")
    C(15, 39, "|")
    C(15, 40, "b")
    C(15, 41, "r")
    C(15, 42, "s")
    C(15, 43, "M")
    C(15, 44, "<")
    C(14, 44, "v")
    C(14, 45, "v")
    C(14, 46, "v")

    C(14, 49, "r")
    C(14, 50, "s")
    C(14, 51, "X")
    C(13, 51, "x")
    C(13, 50, "W")
    C(13, 49, "-")
    C(13, 48, "M")
    C(13, 47, "]")
    C(13, 46, ">")
    C(13, 52, "]")
    C(13, 53, "<")
    C(12, 53, "^")
    C(12, 45, ">")

    C(15, 51, "W")
    C(16, 51, "X")
    C(16, 52, ">")
    C(24, 52, "^")
    C(16, 50, ">")
    C(24, 50, "^")
    C(24, 24, "<")

    C(17, 51, ">")
    C(18, 51, "v")
    C(18, 56, ">")
    C(20, 56, "r")
    C(21, 56, "M")
    C(22, 56, str(PARTITION_BITS))
    C(23, 56, "W")
    C(24, 56, "{")
    C(25, 56, "M")
    C(26, 56, "`")
    C(27, 56, digits[0])
    C(28, 56, digits[1])
    C(29, 56, "`")
    C(30, 56, "W")
    C(31, 56, "|")
    C(32, 56, "v")
    C(32, 59, ">")

    C(16, 26, "0")
    C(17, 26, ">")
    C(30, 26, "v")
    C(30, 59, ">")
    C(45, 59, "s")
    C(46, 59, "H")

    candidate_x = ox + 53
    p.pipe(
        [
            (ox + 52, oy + 59),
            (candidate_x, oy + 59),
            (candidate_x, COLLECTOR_Y - 1),
        ]
    )
    return candidate_x


def build_collector(builder, right, candidate_columns):
    p = builder.program
    C0 = builder.cell
    ox, oy = 0, COLLECTOR_Y

    def C(x, y, char):
        C0(ox + x, oy + y, char)

    builder.room(10, oy, right - 10, 92)
    builder.room(2, oy + 40, 7, 5)
    p.pipe(
        [(9, oy + 85), (1, oy + 85), (1, oy + 46), (5, oy + 46), (5, oy + 45)]
    )
    p.pipe([(4, oy + 39), (4, oy + 20), (9, oy + 20)])
    C(3, 41, ">")
    builder.man(4, oy + 41)
    C(5, 41, "R")
    C(6, 41, "s")
    C(7, 41, "v")
    C(7, 42, "<")
    C(3, 42, "^")

    builder.man(12, oy + 2)
    C(13, 2, ">")
    C(34, 2, "r")
    C(35, 2, "b")
    C(36, 2, "1")
    C(37, 2, "N")
    C(38, 2, "v")
    C(38, 3, "<")
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
    C(35, 15, "v")
    C(35, 16, "<")
    C(15, 16, "s")
    C(14, 16, "v")
    C(14, 19, "r")
    C(14, 20, "s")
    C(14, 21, "X")
    C(13, 21, "^")
    C(13, 18, ">")
    C(14, 18, "v")
    C(15, 21, "0")
    C(16, 21, "M")
    C(17, 21, "^")
    C(17, 8, ">")

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

    end_x = candidate_columns[-1] + 12
    C(end_x, 8, "W")
    C(end_x + 1, 8, "v")
    C(end_x + 1, 14, "<")
    C(16, 14, "v")
    C(16, 33, "X")

    C(15, 33, "<")
    C(14, 33, "s")
    C(13, 33, "v")
    C(14, 34, "v")
    C(14, 35, "r")
    C(14, 36, "s")
    C(14, 37, "X")
    C(13, 37, "^")
    C(13, 34, ">")
    C(15, 37, "v")
    C(15, 45, "<")
    C(14, 45, "v")

    C(16, 34, "v")
    C(16, 39, ">")
    C(60, 39, "v")
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

    p.output_room(44, oy + 94)
    p.pipe([(45, oy + 92), (45, oy + 93)])


def build():
    builder = Builder()
    worker_bases = [WORKER_X0 + index * WORKER_GAP for index in range(len(WORKER_IDS))]
    candidate_columns = [base + 53 for base in worker_bases]
    collector_right = candidate_columns[-1] + 24
    broadcast_outputs = [(34, COLLECTOR_Y - 1)] + [
        (base + 34, WORKER_Y - 1) for base in worker_bases
    ]
    build_broadcaster(builder, collector_right, broadcast_outputs)
    built_candidates = [
        build_worker(builder, base, worker_id)
        for worker_id, base in zip(WORKER_IDS, worker_bases)
    ]
    build_collector(builder, collector_right, built_candidates)
    return builder.program


if __name__ == "__main__":
    program = build()
    destination = Path(__file__).with_name("parallel64.man")
    program.save(str(destination))
    print(program.render())
    print("footprint", program.footprint())
