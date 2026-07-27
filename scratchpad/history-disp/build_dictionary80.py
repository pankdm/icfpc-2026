#!/usr/bin/env python3
"""Route-B dictionary block, already packed to its final 80x9 footprint.

The preload order is bottom-to-top.  That makes the seventh (last) data row
eastbound, so the steady r/s pump fits in the three spare columns at the
upper-right instead of costing two more rows.

Three unsent slots are deliberately interspersed in group B.  They let the
six recycled phrases remain ring positions 17..22 while clustering the wide
escape entries into the same physical columns.  The resulting group-B profile
uses 70 of the 73 cells available before the pump:

    TB = [15, 17, 8, 13, 2]
    sum(TB) + 3 * len(TB) = 70

Run from anywhere:

    python3 scratchpad/history-disp/build_dictionary80.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "solutions", "history-lesson"))

from littleman import Program                       # noqa: E402
import build_ring as base                           # noqa: E402

WIDTH = 80
RUN = (60, 65)
GROUP_B_TEMPLATE = [
    [5, 4, 4, 5, None],
    [None, 5, 4, 17, 13],
    [15, 17, 2, 9, None],
    [2, 13, 8, 11, 15],
    [15, 17, 7, 13, 1],       # final 1 is the zero sentinel's slot width
]


def build_encoding():
    """Return symbols, ring values, and the packed group-B rows.

    Non-None template cells are consumed in preload-walk order.  The first
    six take direct phrases, the next fifteen take escape phrases, and the
    final cell is the zero sentinel.
    """
    low_free = list(base.SMALL_FREE)
    recycled = list(range(RUN[0], RUN[1] + 1))
    base.SMALL_FREE = low_free + recycled
    try:
        stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
    finally:
        base.SMALL_FREE = low_free

    singles = [i for i, (_, single) in enumerate(phrases) if single is True]
    pairs = [i for i, (_, single) in enumerate(phrases) if single is False]
    assert len(singles) == len(low_free) + len(recycled)
    assert len(pairs) == 15

    value = {
        i: base.pack128(base.phrase_bytes(phrases[i][0]))
        for i in singles + pairs
    }
    low = singles[:len(low_free)]
    high = singles[len(low_free):]

    ring = {}
    slot_of = {}
    for i, position in zip(low, low_free):
        ring[position] = value[i]
        slot_of[i] = ("low", position)
    for position in range(1, 17):
        ring.setdefault(position, base.pack128(base.spell(position)))

    by_width = {}
    for i in high:
        by_width.setdefault(len(str(value[i])), []).append(i)
    pair_by_width = {}
    for i in pairs:
        pair_by_width.setdefault(len(str(value[i])), []).append(i)

    logical = []
    send_number = 0
    for row in GROUP_B_TEMPLATE:
        cells = []
        for wanted_width in row:
            if wanted_width is None:
                cells.append(None)
                continue
            if send_number < len(high):
                source = by_width[wanted_width].pop()
                position = 17 + send_number
                slot_of[source] = ("high", position + 43)
                ring[position] = value[source]
                cells.append(value[source])
            elif send_number < len(high) + len(pairs):
                source = pair_by_width[wanted_width].pop()
                position = 17 + send_number
                slot_of[source] = ("pair", position)
                ring[position] = value[source]
                cells.append(value[source])
            else:
                assert send_number == len(high) + len(pairs)
                cells.append(0)
            send_number += 1
        logical.append(cells)
    assert send_number == len(high) + len(pairs) + 1
    assert all(not remaining for remaining in by_width.values())
    assert all(not remaining for remaining in pair_by_width.values())
    assert sorted(ring) == list(range(1, 38))

    symbols = []
    for token in stream:
        if token >= 0:
            symbols.append(token)
            continue
        kind, code = slot_of[-token - 1]
        symbols.extend([base.ESC, code] if kind == "pair" else [code])

    # Semantic counterpart of Route B's classifier.
    decoded = []
    i = 0
    while i < len(symbols):
        symbol = symbols[i]
        i += 1
        if symbol == 0:
            decoded.append(0)
        elif symbol <= 16:
            decoded.append(ring[symbol])
        elif symbol == base.ESC:
            decoded.append(ring[symbols[i]])
            i += 1
        elif RUN[0] <= symbol <= RUN[1]:
            decoded.append(ring[symbol - 43])
        else:
            decoded.append(symbol + 31)
    output = bytearray()
    year = base.pack128(f"; {base.FIRST_YEAR}: ".encode())
    decade = 10
    for packed in decoded:
        if packed == 0:
            packed, year, decade = year, year + base.STEP, decade - 1
            if decade == 0:
                year += base.CORR
                decade = 10
        while packed:
            packed, byte = divmod(packed, base.B2)
            output.append(byte)
    assert bytes(output) == base.TEXT
    assert len(symbols) == 1951
    return symbols, ring, logical


def _place_row(program, y, values, widths, east):
    starts = []
    x = 2
    for width in widths:
        starts.append(x)
        x += width + 3
    for start, value, width in zip(starts, values, widths):
        if value is None:
            digits = "0" * width
            cells = (["`", *digits, "`", " "] if east
                     else [" ", "`", *digits[::-1], "`"])
        else:
            digits = str(value).zfill(width)
            cells = (["`", *digits, "`", "s"] if east
                     else ["s", "`", *digits[::-1], "`"])
        px = start + 1 if east else start
        base.put_row(program, px, y, cells)
    return x + 1


def build():
    symbols, ring, group_b = build_encoding()
    smalls = [ring[position] for position in range(1, 17)]
    # Logical traversal starts at the bottom and alternates E,W,...,E.
    grid_a, widths_a, rows_a, _ = base.group_a_grid(
        smalls, west_first=False, inner=73
    )
    assert rows_a == 2

    widths_b = []
    for column in range(5):
        physical_values = []
        for logical_row, row in enumerate(group_b):
            physical_column = column if logical_row % 2 == 0 else 4 - column
            value = row[physical_column]
            if value is not None:
                physical_values.append(len(str(value)))
        widths_b.append(max(physical_values, default=1))
    assert widths_b == [15, 17, 8, 13, 2], widths_b
    assert sum(widths_b) + 3 * len(widths_b) == 70

    rows = []
    for logical_row in range(rows_a):
        rows.append((grid_a[logical_row], widths_a))
    for logical_row, walk_values in enumerate(group_b):
        physical = (
            walk_values if logical_row % 2 == 0 else walk_values[::-1]
        )
        rows.append((physical, widths_b))
    assert len(rows) == 7

    program = Program()
    program.room(0, 0, WIDTH, 9)
    spans = [sum(width + 3 for width in widths) for _, widths in rows]
    turn = 3 + max(spans)
    assert turn + 3 <= WIDTH - 2, (turn, WIDTH)

    # Logical row zero is physically at the bottom.  The preload snake climbs.
    for logical_row, (values, widths) in enumerate(rows):
        y = 7 - logical_row
        east = logical_row % 2 == 0
        _place_row(program, y, values, widths, east)
        final = logical_row == len(rows) - 1
        if east:
            if logical_row:
                program.put(1, y, ">")
            program.put(turn, y, ">" if final else "^")
        else:
            program.put(turn, y, "<")
            program.put(1, y, "^")

    # Enter the steady pump eastbound from the final preload row.
    base.put_row(program, turn + 1, 1, [">", "r", "v"])
    base.put_row(program, turn + 1, 2, ["^", "s", "<"])
    program.put(1, 7, "@")

    bad = base.audit_vertical_ticks(program)
    assert not bad, f"vertical tick audit failed: {bad[:4]}"
    bands = base.optimize_feeder(symbols, WIDTH)
    feeder_rows = sum(band.rows for band in bands)
    assert feeder_rows == 61
    return program, ring, feeder_rows


if __name__ == "__main__":
    result, ring, feeder_rows = build()
    output = os.path.join(HERE, "dictionary-80x9.man")
    result.save(output)
    assert result.footprint() == (80, 9, 6400)
    print(
        f"wrote {output}: 80x9, {len(ring)} ring entries, "
        f"{feeder_rows} feeder rows"
    )
