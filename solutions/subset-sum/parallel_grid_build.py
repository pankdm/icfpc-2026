#!/usr/bin/env python3
"""Fold the parallel subset-sum workers into chained horizontal rows."""

import math
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parallel8_build as base


WORKERS = int(os.environ.get("SS_WORKERS", "64"))
ROWS = int(os.environ.get("SS_ROWS", "4"))
if WORKERS < 1 or WORKERS > 256 or WORKERS & (WORKERS - 1):
    raise ValueError("SS_WORKERS must be a power of two between 1 and 256")
if ROWS < 1 or ROWS > 16 or ROWS > WORKERS:
    raise ValueError("SS_ROWS must be between 1 and min(16, SS_WORKERS)")

WORKER_X0 = 5
ROW_STRIDE = 71
BROADCAST_Y = 0
WORKER_Y = 7
COLLECTOR_Y = 64


def compare_station(builder, x, y):
    C = builder.cell
    C(x, y, "r")
    C(x + 1, y, "-")
    C(x + 2, y, "X")
    C(x + 2, y - 1, ">")
    C(x + 7, y - 1, "v")
    C(x + 2, y + 1, "+")
    C(x + 2, y + 2, "M")
    C(x + 2, y + 3, ">")
    C(x + 7, y + 3, "^")
    C(x + 7, y, ">")


def build_row_broadcaster(builder, y, room_right, worker_bases, worker_y, preprocess):
    p = builder.program
    C = builder.cell
    builder.room(10, y, room_right - 10, 5)
    builder.man(12, y + 2)
    if preprocess:
        C(13, y + 2, "r")
        C(14, y + 2, "b")
        C(15, y + 2, "S")
        C(16, y + 2, "M")
        C(17, y + 2, "1")
        C(18, y + 2, "{")
        C(19, y + 2, "M")
        C(20, y + 2, str(base.PARTITION_BITS))
        C(21, y + 2, "W")
        C(22, y + 2, "}")
        C(23, y + 2, "S")
        C(24, y + 2, "1")
        C(25, y + 2, "N")
        C(26, y + 2, "S")
        C(27, y + 2, ">")
        C(28, y + 2, "r")
        C(29, y + 2, "S")
        C(30, y + 2, "v")
        C(30, y + 3, "<")
        C(27, y + 3, "^")
    else:
        C(13, y + 2, "r")
        C(14, y + 2, "S")
        C(15, y + 2, "v")
        C(15, y + 3, "<")
        C(11, y + 3, "^")
        C(11, y + 2, ">")
    for worker_base in worker_bases:
        p.pipe([(worker_base + 33, y + 5), (worker_base + 33, worker_y - 1)])


def build_local_collector(builder, y, room_right, candidate_columns):
    p = builder.program
    C = builder.cell
    builder.room(10, y, room_right - 10, 7)
    builder.man(12, y + 2)
    C(13, y + 2, "0")
    C(14, y + 2, "M")
    for column in candidate_columns:
        compare_station(builder, column, y + 2)
    end_x = candidate_columns[-1] + 12
    C(end_x, y + 2, "W")
    C(end_x + 1, y + 2, "v")
    C(end_x + 1, y + 5, ">")
    C(room_right - 5, y + 5, "s")
    C(room_right - 4, y + 5, "H")
    return (room_right, y + 5)


def build():
    builder = base.Builder()
    p = builder.program
    worker_ids = list(range(WORKERS))
    columns = math.ceil(WORKERS / ROWS)
    worker_bases = [WORKER_X0 + index * base.WORKER_GAP for index in range(columns)]
    last_candidate = worker_bases[-1] + 48
    prior_column = last_candidate + 20
    room_right = prior_column + 24

    row_ids = [worker_ids[index * columns : (index + 1) * columns] for index in range(ROWS)]
    row_ids = [ids for ids in row_ids if ids]
    collector_sources = []

    for row_index, ids in enumerate(row_ids):
        row_y = row_index * ROW_STRIDE
        broadcaster_y = row_y + BROADCAST_Y
        worker_y = row_y + WORKER_Y
        collector_y = row_y + COLLECTOR_Y
        bases = worker_bases[: len(ids)]
        build_row_broadcaster(
            builder, broadcaster_y, room_right, bases, worker_y, row_index == 0
        )
        candidate_columns = [
            base.build_worker(builder, worker_base, worker_id, worker_y, collector_y)
            for worker_base, worker_id in zip(bases, ids)
        ]

        if row_index < len(row_ids) - 1:
            if row_index:
                candidate_columns.append(prior_column)
            collector_sources.append(
                build_local_collector(builder, collector_y, room_right, candidate_columns)
            )
        else:
            if row_index:
                candidate_columns.append(prior_column)
            base.build_collector(builder, room_right, candidate_columns, collector_y)

    first_y = BROADCAST_Y
    p.input_room(20, first_y - 5)
    p.pipe([(21, first_y - 2), (21, first_y - 1)])

    for row_index in range(len(row_ids) - 1):
        source_y = row_index * ROW_STRIDE + BROADCAST_Y + 4
        destination_y = (row_index + 1) * ROW_STRIDE + BROADCAST_Y + 3
        p.pipe([(9, source_y), (5, source_y), (5, destination_y), (9, destination_y)])

    final_collector_y = (len(row_ids) - 1) * ROW_STRIDE + COLLECTOR_Y
    last_broadcaster_y = (len(row_ids) - 1) * ROW_STRIDE + BROADCAST_Y
    p.pipe(
        [
            (9, last_broadcaster_y + 4),
            (4, last_broadcaster_y + 4),
            (4, final_collector_y - 2),
            (34, final_collector_y - 2),
            (34, final_collector_y - 1),
        ]
    )

    for row_index, source in enumerate(collector_sources):
        next_collector_y = (row_index + 1) * ROW_STRIDE + COLLECTOR_Y
        p.pipe(
            [
                source,
                (room_right + 1, source[1]),
                (room_right + 1, next_collector_y - 2),
                (prior_column, next_collector_y - 2),
                (prior_column, next_collector_y - 1),
            ]
        )

    return builder.program


if __name__ == "__main__":
    program = build()
    destination = HERE / f"parallel{WORKERS}-r{ROWS}.man"
    program.save(str(destination))
    print(program.render())
    print("footprint", program.footprint())
