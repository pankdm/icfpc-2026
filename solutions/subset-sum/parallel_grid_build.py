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

WORKER_X0 = 10 if base.PREFIX_MODE and base.COMPACT_WORKER else 8
COMPACT_WIDTH_DELTA = 4 * (base.PARTITION_BITS - 6) if base.COMPACT_WORKER else 0
WORKER_GAP = (
    31 + COMPACT_WIDTH_DELTA
    if base.PREFIX_MODE and base.COMPACT_WORKER
    else base.WORKER_GAP
)
ROW_STRIDE = (
    46
    if base.PREFIX_MODE and base.COMPACT_WORKER
    else (66 if base.PREFIX_MODE else 68)
)
BROADCAST_Y = 0
WORKER_Y = 6
COLLECTOR_Y = 40 if base.PREFIX_MODE and base.COMPACT_WORKER else 60
PRIOR_COLUMN = 15 if base.PREFIX_MODE and base.COMPACT_WORKER else 30
PRIOR_ATTACHMENT_X = (
    15 if base.PREFIX_MODE and base.COMPACT_WORKER else 17
)
FINAL_PRIOR_COLUMN = 30
FINAL_PRIOR_ATTACHMENT_X = (
    29 if base.PREFIX_MODE and base.COMPACT_WORKER else 17
)


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
    builder.room(10, y, room_right - 10, 4)
    builder.man(12, y + 1)
    if preprocess:
        C(13, y + 1, "r")
        C(14, y + 1, "b")
        C(15, y + 1, "S")
        C(16, y + 1, "M")
        C(17, y + 1, "1")
        C(18, y + 1, "{")
        C(19, y + 1, "M")
        C(20, y + 1, str(base.PARTITION_BITS))
        C(21, y + 1, "W")
        C(22, y + 1, "}")
        if base.PREFIX_MODE:
            C(23, y + 1, "M")
            C(25, y + 1, "1")
            C(26, y + 1, "N")
            C(27, y + 1, "S")
            C(28, y + 1, ">")
            C(29, y + 1, "r")
            C(30, y + 1, "S")
            C(31, y + 1, "m")
            C(32, y + 1, "d")
            C(32, y + 2, "<")
            C(28, y + 2, "^")
            C(33, y + 1, "r")
            C(34, y + 1, "S")
            C(35, y + 1, "W")
            C(36, y + 1, "S")
            C(37, y + 1, "H")
        else:
            C(23, y + 1, "S")
            C(24, y + 1, "1")
            C(25, y + 1, "N")
            C(26, y + 1, "S")
            C(27, y + 1, ">")
            C(28, y + 1, "r")
            C(29, y + 1, "S")
            C(30, y + 1, "v")
            C(30, y + 2, "<")
            C(27, y + 2, "^")
    else:
        C(13, y + 1, "r")
        C(14, y + 1, "S")
        C(15, y + 1, "v")
        C(15, y + 2, "<")
        C(11, y + 2, "^")
        C(11, y + 1, ">")
    input_offset = (
        16 + COMPACT_WIDTH_DELTA
        if base.PREFIX_MODE and base.COMPACT_WORKER
        else 33
    )
    for worker_base in worker_bases:
        p.pipe(
            [
                (worker_base + input_offset, y + 4),
                (worker_base + input_offset, worker_y - 1),
            ]
        )


def build_local_collector(builder, y, room_right, candidate_columns):
    p = builder.program
    C = builder.cell
    height = 4 if base.PREFIX_MODE else 8
    man_y = y + 1 if base.PREFIX_MODE else y + 2
    builder.room(10, y, room_right - 10, height)
    builder.man(12, man_y)
    end_x = candidate_columns[-1] + 12
    if base.PREFIX_MODE:
        C(13, y + 1, ">")
        for column in candidate_columns:
            C(column, y + 1, "r")
            C(column + 1, y + 1, "X")
            C(column + 1, y + 2, ">")
        C(end_x - 1, y + 1, "0")
        C(end_x, y + 1, "v")
        C(end_x, y + 2, ">")
        C(end_x + 1, y + 2, "s")
        C(end_x + 2, y + 2, "H")
        return (end_x + 1, y + 4)
    else:
        C(13, y + 2, "0")
        C(14, y + 2, "M")
        for column in candidate_columns:
            compare_station(builder, column, y + 2)
        C(end_x, y + 2, "W")
        C(end_x + 1, y + 2, "v")
    C(end_x + 1, y + 6, "<")
    C(14, y + 6, "s")
    C(13, y + 6, "H")
    return (9, y + 6)


def build():
    builder = base.Builder()
    p = builder.program
    worker_ids = list(range(WORKERS - 1, -1, -1)) if base.PREFIX_MODE else list(range(WORKERS))
    columns = math.ceil(WORKERS / ROWS)
    worker_bases = [WORKER_X0 + index * WORKER_GAP for index in range(columns)]
    candidate_offset = (
        30 + COMPACT_WIDTH_DELTA
        if base.PREFIX_MODE and base.COMPACT_WORKER
        else 48
    )
    last_candidate = worker_bases[-1] + candidate_offset
    room_right = last_candidate + 16

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
                candidate_columns.insert(0, PRIOR_COLUMN)
            collector_sources.append(
                build_local_collector(builder, collector_y, room_right, candidate_columns)
            )
        else:
            if row_index:
                candidate_columns.insert(0, FINAL_PRIOR_COLUMN)
            base.build_collector(builder, room_right, candidate_columns, collector_y)

    first_y = BROADCAST_Y
    p.input_room(5, first_y)
    p.pipe([(8, first_y + 1), (9, first_y + 1)])

    for row_index in range(len(row_ids) - 1):
        source_y = row_index * ROW_STRIDE + BROADCAST_Y + 2
        destination_y = (row_index + 1) * ROW_STRIDE + BROADCAST_Y + 1
        p.pipe(
            [
                (room_right, source_y),
                (room_right + 1, source_y),
                (room_right + 1, destination_y),
                (room_right, destination_y),
            ]
        )

    final_collector_y = (len(row_ids) - 1) * ROW_STRIDE + COLLECTOR_Y
    last_broadcaster_y = (len(row_ids) - 1) * ROW_STRIDE + BROADCAST_Y
    p.pipe(
        [
            (room_right, last_broadcaster_y + 2),
            (room_right + 1, last_broadcaster_y + 2),
            (room_right + 1, final_collector_y + 6),
            (room_right, final_collector_y + 6),
        ]
    )

    for row_index, source in enumerate(collector_sources):
        next_collector_y = (row_index + 1) * ROW_STRIDE + COLLECTOR_Y
        prior_attachment_x = (
            FINAL_PRIOR_ATTACHMENT_X
            if row_index + 1 == len(row_ids) - 1
            else PRIOR_ATTACHMENT_X
        )
        route = [source]
        if base.PREFIX_MODE:
            route.append((source[0], source[1] + 1))
            route.append((8, source[1] + 1))
        else:
            route.append((8, source[1]))
        route.extend(
            [
                (8, next_collector_y - 2),
                (prior_attachment_x, next_collector_y - 2),
                (prior_attachment_x, next_collector_y - 1),
            ]
        )
        p.pipe(route)

    return builder.program


if __name__ == "__main__":
    program = build()
    suffix = "-prefix" if base.PREFIX_MODE else ""
    if base.COMPACT_WORKER:
        suffix += "-compact"
    destination = HERE / f"parallel{WORKERS}{suffix}-r{ROWS}.man"
    program.save(str(destination))
    print(program.render())
    print("footprint", program.footprint())
