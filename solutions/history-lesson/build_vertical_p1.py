#!/usr/bin/env python3
"""Alternative History Lesson build: no YEAR room, tall P1 dictionary.

The year prefixes are ordinary stream text.  Direct dictionary slots spell
``"; 20"`` and ``": "``; the final two year digits use raw shifted ASCII
(zero uses one escaped dictionary entry because bare symbol 17 is reserved by
the existing dispatcher).

P1 is turned into a tall, narrow preload room.  One man loads its paired
literal rows, sends the sentinel, and then becomes the steady ring pump.
"""
from __future__ import annotations

import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

from littleman import Program

import build_ring as base


WIDTH = 81
EXTRA_PHRASES = 6

# Logical dictionary entries can be permuted physically.  The first sixteen
# remain direct positions; the rest remain escaped positions.  This order was
# selected to make paired decimal widths fit the tall P1 room.
LOGICAL_ORDER = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    39, 42, 26, 32, 19, 23, 29, 30, 44, 17, 22, 28, 25, 24,
    38, 27, 40, 35, 33, 41, 37, 36, 43, 18, 21, 34, 31, 20,
]
PAIR_SLOTS = (3, 4, 3, 3, 2, 2, 3, 2)
PAIR_CAPS = (43, 45, 45, 45, 45, 45, 45, 43)

def narrow_dispatcher_rows():
    """Remove the unused column immediately before DISP's ring subsystem."""
    rows = []
    for y, row in enumerate(base.DISP_ROWS):
        cells = {x: ch for x, ch in enumerate(row) if ch != " "}
        if y >= 3:
            cells = {(x - 1 if x >= 12 else x): ch for x, ch in cells.items()}
        rows.append("".join(cells.get(x, " ") for x in range(23)))
    assert max(len(row) for row in rows) == 23
    return rows


DISP_NARROW_ROWS = narrow_dispatcher_rows()


def delayed_dispatcher_rows():
    """Give the vertical dictionary time to finish its one-shot preload.

    The old wide P1 finishes before DISP's first lookup.  Reorienting those
    constants vertically lengthens the preload walk, so DISP starts with an
    81-lap countdown in the otherwise empty right side of its room.
    """
    rows = [list(" " * 23) for _ in range(3)]
    rows[0][12:23] = list("@9M*b>    v")
    rows[2][0] = "v"
    rows[2][17] = "d"
    rows[2][18] = "m"
    rows[2][22] = "<"
    logic = [list(row.ljust(23)) for row in DISP_NARROW_ROWS]
    assert logic[0][1] == "@"
    logic[0][1] = " "
    return ["".join(row) for row in rows + logic]


DISP_DELAYED_ROWS = delayed_dispatcher_rows()


def build_encoding(extra_phrases=EXTRA_PHRASES):
    symbols, logical_ring, _ = base.build_encoding(
        extra_pair_count=extra_phrases
    )

    # Replace two low-value direct entries with the shared year affixes.
    old_prefix_slot = max(logical_ring) + 1
    old_suffix_slot = old_prefix_slot + 1
    zero_digit_slot = old_prefix_slot + 2
    logical_ring[old_prefix_slot] = logical_ring[9]
    logical_ring[old_suffix_slot] = logical_ring[15]
    logical_ring[zero_digit_slot] = base.pack128(b"0")
    logical_ring[9] = base.pack128(b"; 20")
    logical_ring[15] = base.pack128(b": ")
    dictionary_words = 38 + extra_phrases
    assert sorted(logical_ring) == list(range(1, dictionary_words + 1))
    if extra_phrases == EXTRA_PHRASES:
        logical_order = LOGICAL_ORDER
    else:
        # Preserve as much of the tuned 44-word order as exists, then append
        # any new logical positions.  The layout-builder is free to repack
        # these physical values into its independently optimized bands.
        logical_order = [
            logical for logical in LOGICAL_ORDER
            if logical <= dictionary_words
        ]
        logical_order.extend(
            logical for logical in range(1, dictionary_words + 1)
            if logical not in logical_order
        )
    assert sorted(logical_order) == list(range(1, dictionary_words + 1))

    logical_symbols = []
    year = base.FIRST_YEAR
    for symbol in symbols:
        if symbol == 0:
            logical_symbols.append(9)
            for digit in str(year)[2:]:
                shifted = ord(digit) - 31
                if shifted == 17:
                    logical_symbols.extend([base.ESC, zero_digit_slot])
                else:
                    logical_symbols.append(shifted)
            logical_symbols.append(15)
            year += 1
        elif symbol == 9:
            logical_symbols.extend([base.ESC, old_prefix_slot])
        elif symbol == 15:
            logical_symbols.extend([base.ESC, old_suffix_slot])
        else:
            logical_symbols.append(symbol)
    assert year == base.LAST_YEAR + 1

    new_position = {
        logical: physical
        for physical, logical in enumerate(logical_order, start=1)
    }
    ring = {
        new_position[logical]: value
        for logical, value in logical_ring.items()
    }

    physical_symbols = []
    i = 0
    while i < len(logical_symbols):
        symbol = logical_symbols[i]
        i += 1
        if symbol == base.ESC:
            physical_symbols.extend(
                [base.ESC, new_position[logical_symbols[i]]]
            )
            i += 1
        elif 1 <= symbol <= 16:
            physical_symbols.append(new_position[symbol])
        else:
            physical_symbols.append(symbol)

    # Semantic verification of the no-YEAR pipeline.
    values = []
    i = 0
    while i < len(physical_symbols):
        symbol = physical_symbols[i]
        i += 1
        if symbol == base.ESC:
            values.append(ring[physical_symbols[i]])
            i += 1
        elif symbol <= 16:
            values.append(ring[symbol])
        else:
            values.append(symbol + 31)
    output = bytearray()
    for value in values:
        while value:
            value, byte = divmod(value, base.B2)
            output.append(byte)
    assert bytes(output) == base.TEXT

    bands = base.optimize_feeder(physical_symbols, WIDTH)
    if extra_phrases == EXTRA_PHRASES:
        assert len(bands) == 32
    return physical_symbols, ring, bands


def table_bands(ring):
    values = [ring[position] for position in range(1, 45)]
    bands = []
    cursor = 0
    for slots, cap in zip(PAIR_SLOTS, PAIR_CAPS):
        pair = values[cursor:cursor + 2 * slots]
        cursor += 2 * slots
        top = pair[:slots]
        bottom = pair[slots:]
        widths = [
            max(len(str(top[j])), len(str(bottom[slots - 1 - j])))
            for j in range(slots)
        ]
        assert sum(width + 3 for width in widths) <= cap
        bands.append((top, bottom, widths))
    assert cursor == len(values)
    return bands


def place_vertical_p1(program, x0, y0, ring):
    """Place a 52x20 P1 room, then route its loader into the ring pump."""
    width, height = 52, 20
    program.room(x0, y0, width, height)
    bands = table_bands(ring)

    def place_pair(band_index, top, bottom, widths):
        top_y_local = y0 + 2 + 2 * band_index
        bottom_y = top_y_local + 1
        # Leave column 1 for the west-row descent.  Starting slots there
        # would overwrite the first send in every paired band.
        base_x = x0 + (2 if band_index < len(bands) - 1 else 4)
        starts = []
        cursor = base_x
        for width_ in widths:
            starts.append(cursor)
            cursor += width_ + 3
        for j, (value, width_) in enumerate(zip(top, widths)):
            base.put_row(
                program,
                starts[j] + 1,
                top_y_local,
                base.p1_slot_cells(value, width_, True),
            )
        physical_bottom = list(reversed(bottom))
        for j, (value, width_) in enumerate(zip(physical_bottom, widths)):
            base.put_row(
                program,
                starts[j],
                bottom_y,
                base.p1_slot_cells(value, width_, False),
            )
        if band_index == 0:
            program.put(x0 + 1, top_y_local, "@")
        else:
            program.put(x0 + 1, top_y_local, ">")
        turn_x = x0 + (44 if band_index == 0 else 47)
        program.put(turn_x, top_y_local, "v")
        program.put(turn_x, bottom_y, "<")
        if band_index < len(bands) - 1:
            program.put(x0 + 1, bottom_y, "v")
        else:
            # After the final entry, send the sentinel and descend to the
            # return row that climbs the right-side bus into the pump.
            program.put(x0 + 3, bottom_y, "0")
            program.put(x0 + 2, bottom_y, "s")
            program.put(x0 + 1, bottom_y, "v")

    for band_index, band in enumerate(bands):
        place_pair(band_index, *band)

    return_y = y0 + 18
    program.put(x0 + 1, return_y, ">")
    program.put(x0 + 50, return_y, "^")

    # Once preload and the sentinel are complete, the same man reaches this
    # steady pump.  This ordering is essential: an eagerly spawned pump can
    # interleave returned words with the unfinished preload.
    pump_y = y0 + 1
    program.put(x0 + 50, pump_y, "<")
    program.put(x0 + 49, pump_y, "<")
    program.put(x0 + 48, pump_y, "r")
    program.put(x0 + 47, pump_y, "s")
    program.put(x0 + 46, pump_y, "v")
    program.put(x0 + 46, y0 + 2, ">")
    program.put(x0 + 47, y0 + 2, ">")
    program.put(x0 + 48, y0 + 2, ">")
    program.put(x0 + 49, y0 + 2, "^")


def build():
    _, ring, bands = build_encoding()
    probe = Program()
    feeder_rows = base.variable_feeder(probe, bands, WIDTH)
    assert feeder_rows == 64, feeder_rows
    tail = feeder_rows + 2
    assert tail == 66

    # Keep the first working version spacious so each pipe binding is clear.
    program = Program()
    base.variable_feeder(program, bands, WIDTH)
    place_vertical_p1(program, 0, tail, ring)
    # Grow DISP upward: its original logic stays at the baseline absolute
    # coordinates, while the countdown occupies three new rows above it.
    base.paste_room(program, 56, tail + 9, DISP_DELAYED_ROWS)
    base.paste_room(program, 56, tail, base.DECODER_ROWS)
    base.paste_room(program, 69, tail, base.UNPACK_ROWS)
    program.output_room(69, tail + 6)

    # feeder -> DECODER
    program.pipe([(55, tail), (55, tail + 2)], end_direction="E")
    # DECODER -> DISP (down the right edge of the central routing strip)
    program.pipe([
        (61, tail + 4),
        (61, tail + 8),
        (54, tail + 8),
        (54, tail + 14),
        (55, tail + 14),
    ], end_direction="E")
    # DISP -> UNPACK
    program.pipe([
        (74, tail + 8),
        (74, tail + 5),
        (79, tail + 5),
        (79, tail + 4),
    ], end_direction="N")
    # UNPACK -> output
    program.pipe([
        (73, tail + 4),
        (73, tail + 5),
        (70, tail + 5),
    ], end_direction="S")
    # P1 -> DISP: route under the rooms so the incoming attachment sits beside
    # DISP's hot ring receives rather than its stream receive.
    program.pipe([
        (52, tail + 16),
        (53, tail + 16),
        (53, tail + 22),
        (76, tail + 22),
        (76, tail + 21),
        (54, tail + 21),
        (54, tail + 20),
        (74, tail + 20),
    ], end_direction="N")
    # DISP -> P1: the prototype takes the spacious route below both rooms.
    program.pipe([
        (78, tail + 20),
        (78, tail + 23),
        (40, tail + 23),
        (40, tail + 20),
    ], end_direction="N")

    bad = base.audit_vertical_ticks(program)
    assert not bad, f"vertical tick audit failed: {bad[:4]}"
    return program


def main():
    program = build()
    out = os.path.join(HERE, "candidates", "81x90-vertical-p1.man")
    program.save(out)
    width, height, score = program.footprint()
    print(f"wrote {out}: {width}x{height} score={score}")


if __name__ == "__main__":
    main()
