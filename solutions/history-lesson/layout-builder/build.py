#!/usr/bin/env python3
"""Build a pipe-free layout scaffold for the vertical-P1 History Lesson design.

This is intentionally not a candidate solution yet.  It places the optimized
feeder, a fixed-width vertical dictionary, and the remaining rooms, but draws
no pipes between them.  The scaffold is useful for experimenting with the
feeder/dictionary geometry before committing to pipe attachment locations.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.dirname(HERE)
TOOLS_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "..", "tools"))
sys.path.insert(0, HISTORY_DIR)
sys.path.insert(0, TOOLS_DIR)

from littleman import Program

import build_vertical_p1 as vertical
import build_vertical_p2 as compact


DEFAULT_FEEDER_WIDTH = 81
DEFAULT_DICTIONARY_WIDTH = 52
DEFAULT_DICTIONARY_WORDS = 44
MIN_DICTIONARY_WORDS = 38
MAX_DICTIONARY_WORDS = 91
LOGGER = logging.getLogger(__name__)

# A physical permutation found by the width-constrained packing search. Direct
# positions remain in the first sixteen slots and escaped positions after
# them, so references can be remapped without changing the stream protocol.
# This order keeps similarly-sized values close enough for the paired-row DP
# to share literal columns efficiently.
PACKING_ORDER_44 = [
    11, 2, 5, 7, 8, 6, 4, 9, 15, 16, 1, 14, 12, 10, 13, 3,
    25, 18, 36, 26, 22, 19, 40, 23, 35, 30, 34, 41, 24, 39,
    31, 27, 29, 32, 17, 20, 44, 37, 38, 21, 43, 33, 28, 42,
]
TOP_LEFT_BLOCK_ROWS = (
    ">rsv",
    "^<<<",
)
TOP_LEFT_BLOCK_WIDTH = 4
RETURN_COLUMN = 1
START_COLUMN = 5
LATER_START_COLUMN = 2

# Port offsets are part of the compact dispatcher's design: its sends and
# receives select the nearest matching pipe, so moving an attachment can
# silently bind an instruction to the wrong service.
DISP_STREAM_IN = (-1, 2)
DISP_STREAM_OUT = (compact.UNPACK_PORT - compact.DISP_X, -1)
DISP_RING_IN = (
    compact.RING_IN_PORT - compact.DISP_X,
    len(compact.DISP_ROWS) + 2,
)
DISP_RING_OUT = (
    compact.RING_OUT_PORT - compact.DISP_X,
    len(compact.DISP_ROWS) + 2,
)


@dataclass(frozen=True)
class DictionaryBand:
    """Two rows of dictionary values sharing aligned literal columns."""

    top_slots: tuple[int | None, ...]
    bottom_slots: tuple[int | None, ...]
    widths: tuple[int, ...]
    constant_count: int


def _slot_width(top: int | None, bottom: int | None) -> int:
    """Source width of one vertically paired literal slot."""
    top_digits = len(str(top)) if top is not None else 1
    bottom_digits = len(str(bottom)) if bottom is not None else 1
    return max(top_digits, bottom_digits)


def _best_band(
    values: tuple[int, ...],
    top_count: int,
    *,
    require_bottom_first: bool = False,
) -> DictionaryBand:
    """Find the narrowest column alignment for one chosen top/bottom split.

    Top constants retain their preload order from left to right. Bottom
    constants are reversed physically because that row is walked right to
    left. The alignment DP may pair a top and bottom literal in one column or
    leave a dummy partner on either row. This removes the old assumption that
    every band has a fixed number of half-and-half slots.
    """
    if not values or not 1 <= top_count <= len(values):
        raise ValueError("invalid dictionary band split")
    top = values[:top_count]
    bottom_physical = tuple(reversed(values[top_count:]))

    @lru_cache(maxsize=None)
    def align(top_index: int, bottom_index: int):
        if top_index == len(top) and bottom_index == len(bottom_physical):
            return (0, ())

        candidates = []
        if top_index < len(top) and bottom_index < len(bottom_physical):
            top_value = top[top_index]
            bottom_value = bottom_physical[bottom_index]
            tail_width, tail_slots = align(top_index + 1, bottom_index + 1)
            candidates.append(
                (
                    _slot_width(top_value, bottom_value) + 3 + tail_width,
                    0,
                    ((top_value, bottom_value),) + tail_slots,
                )
            )
        if top_index < len(top):
            top_value = top[top_index]
            tail_width, tail_slots = align(top_index + 1, bottom_index)
            candidates.append(
                (
                    _slot_width(top_value, None) + 3 + tail_width,
                    1,
                    ((top_value, None),) + tail_slots,
                )
            )
        if bottom_index < len(bottom_physical):
            bottom_value = bottom_physical[bottom_index]
            tail_width, tail_slots = align(top_index, bottom_index + 1)
            candidates.append(
                (
                    _slot_width(None, bottom_value) + 3 + tail_width,
                    2,
                    ((None, bottom_value),) + tail_slots,
                )
            )

        # Prefer the narrowest representation, then fewer columns, then
        # paired columns over top-only and bottom-only columns.
        width, _, slots = min(
            candidates,
            key=lambda candidate: (
                candidate[0],
                len(candidate[2]),
                candidate[1],
            ),
        )
        return width, slots

    _, slots = align(0, 0)
    if require_bottom_first and (not slots or slots[0][1] is None):
        # The special final row needs a real westbound send in its first
        # physical slot, immediately after the sentinel's `vs0` prefix.
        candidates = []
        if top and bottom_physical:
            tail_width, tail_slots = align(1, 1)
            candidates.append(
                (
                    _slot_width(top[0], bottom_physical[0])
                    + 3
                    + tail_width,
                    0,
                    ((top[0], bottom_physical[0]),) + tail_slots,
                )
            )
        if bottom_physical:
            tail_width, tail_slots = align(0, 1)
            candidates.append(
                (
                    _slot_width(None, bottom_physical[0])
                    + 3
                    + tail_width,
                    1,
                    ((None, bottom_physical[0]),) + tail_slots,
                )
            )
        if not candidates:
            raise ValueError("final dictionary band needs a bottom constant")
        _, _, slots = min(
            candidates,
            key=lambda candidate: (
                candidate[0],
                len(candidate[2]),
                candidate[1],
            ),
        )
    top_slots = tuple(slot[0] for slot in slots)
    bottom_slots = tuple(slot[1] for slot in slots)
    widths = tuple(_slot_width(*slot) for slot in slots)
    return DictionaryBand(
        top_slots,
        bottom_slots,
        widths,
        len(values),
    )


def pack_dictionary(values: list[int], room_width: int) -> list[DictionaryBand]:
    """Pack as many constants per paired band as possible with dynamic programming.

    Each slot costs its decimal width plus two backticks and one send cell.
    The outer DP chooses band boundaries. For every boundary candidate, an
    inner alignment DP chooses the top/bottom split and shared literal
    columns. The objective is, in order:

    1. use the fewest paired bands;
    2. put the most constants in earlier bands;
    3. minimize unused cells across those bands.

    Bands are independently right-aligned.
    """
    if room_width < 13:
        raise ValueError("dictionary width must be at least 13")
    # The top-left 2x4 block shifts the first paired band four columns right
    # compared with an ordinary band. Later bands recover that width: column
    # one is the upward return and column two is the ordinary band-to-band
    # descent. On the final bottom row columns two and three send the zero
    # sentinel before the man enters the return.
    first_capacity = room_width - 9
    capacity = room_width - 6
    final_capacity = room_width - 7
    values_tuple = tuple(values)
    max_constants_per_band = 2 * (capacity // 4)

    @lru_cache(maxsize=None)
    def solve(index: int, band_index: int):
        if index == len(values_tuple):
            return (0, (), 0, ())
        best = None
        remaining = len(values_tuple) - index
        for count in range(1, min(remaining, max_constants_per_band) + 1):
            segment = values_tuple[index:index + count]
            final_band = index + count == len(values_tuple)
            band_capacity = capacity
            if band_index == 0:
                band_capacity = first_capacity
            if final_band:
                band_capacity = min(band_capacity, final_capacity)
            # The final band must contain at least one bottom-row constant so
            # the westbound path sends a final value before entering the
            # sentinel and upward return path.
            top_count_stop = count if final_band else count + 1
            for top_count in range(1, top_count_stop):
                band = _best_band(
                    segment,
                    top_count,
                    require_bottom_first=final_band,
                )
                used = sum(width + 3 for width in band.widths)
                if used > band_capacity:
                    continue
                tail = solve(index + count, band_index + 1)
                if tail is None:
                    continue
                candidate = (
                    1 + tail[0],
                    (-count,) + tail[1],
                    (band_capacity - used) + tail[2],
                    (band,) + tail[3],
                )
                if best is None or candidate[:3] < best[:3]:
                    best = candidate
        return best

    result = solve(0, 0)
    if result is None:
        widest = max((len(str(value)) for value in values), default=0)
        raise ValueError(
            f"{len(values)} dictionary words do not fit width {room_width}; "
            f"widest literal has {widest} digits"
        )
    return list(result[3])


def _put_row(program: Program, x: int, y: int, cells) -> None:
    for dx, glyph in enumerate(cells):
        if glyph != " ":
            program.put(x + dx, y, glyph)


def repack_physical_dictionary(
    symbols: list[int],
    ring: dict[int, int],
) -> tuple[list[int], dict[int, int], list[int]]:
    """Permute physical entries and rewrite every dictionary reference."""
    count = len(ring)
    direct_order = PACKING_ORDER_44[:16]
    escaped_order = [
        position for position in PACKING_ORDER_44[16:]
        if position <= count
    ]
    escaped_order.extend(
        position for position in range(17, count + 1)
        if position not in escaped_order
    )
    order = direct_order + escaped_order
    assert sorted(order) == list(range(1, count + 1))

    new_position = {
        old_position: physical_position
        for physical_position, old_position in enumerate(order, start=1)
    }
    assert all(new_position[position] <= 16 for position in range(1, 17))
    assert all(new_position[position] >= 17 for position in range(17, count + 1))

    rewritten = []
    index = 0
    while index < len(symbols):
        symbol = symbols[index]
        index += 1
        if symbol == vertical.base.ESC:
            rewritten.extend([
                symbol,
                new_position[symbols[index]],
            ])
            index += 1
        elif 1 <= symbol <= 16:
            rewritten.append(new_position[symbol])
        else:
            rewritten.append(symbol)

    new_ring = {
        new_position[old_position]: value
        for old_position, value in ring.items()
    }
    return rewritten, new_ring, order


def dictionary_usage(
    symbols: list[int],
    ring: dict[int, int],
) -> list[tuple[int, str, int]]:
    """Return physical slot, decoded word, and reference count for the ring."""
    counts: Counter[int] = Counter()
    index = 0
    while index < len(symbols):
        symbol = symbols[index]
        index += 1
        if symbol == vertical.base.ESC:
            if index >= len(symbols):
                raise ValueError("truncated escaped dictionary reference")
            counts[symbols[index]] += 1
            index += 1
        elif 1 <= symbol <= 16:
            counts[symbol] += 1

    usage = []
    for position in sorted(ring):
        value = ring[position]
        word = bytearray()
        while value:
            value, byte = divmod(value, vertical.base.B2)
            word.append(byte)
        usage.append((position, bytes(word).decode("ascii"), counts[position]))
    return usage


def remove_unused_escaped_entries(
    symbols: list[int],
    ring: dict[int, int],
) -> tuple[list[int], dict[int, int], list[tuple[int, str]]]:
    """Delete unreferenced escaped slots and compact later references.

    Positions 1..16 are protocol-level direct symbols and cannot be removed
    even if a particular stream does not reference them. Positions 17 onward
    are carried after ESC and can therefore be renumbered freely.
    """
    usage = dictionary_usage(symbols, ring)
    removed = [
        (position, word)
        for position, word, references in usage
        if position >= 17 and references == 0
    ]
    if not removed:
        return symbols, ring, []

    removed_positions = {position for position, _ in removed}
    new_position = {}
    next_position = 1
    for old_position in sorted(ring):
        if old_position not in removed_positions:
            new_position[old_position] = next_position
            next_position += 1

    rewritten = []
    index = 0
    while index < len(symbols):
        symbol = symbols[index]
        index += 1
        if symbol == vertical.base.ESC:
            old_position = symbols[index]
            index += 1
            rewritten.extend([symbol, new_position[old_position]])
        else:
            rewritten.append(symbol)

    compacted_ring = {
        new_position[old_position]: value
        for old_position, value in ring.items()
        if old_position in new_position
    }
    return rewritten, compacted_ring, removed


def place_dictionary(
    program: Program,
    x0: int,
    y0: int,
    room_width: int,
    values: list[int],
    bands: list[DictionaryBand] | None = None,
    bottom_padding: int = 0,
) -> tuple[int, int]:
    """Place a right-aligned vertical-P1 dictionary and return (width, height)."""
    if bands is None:
        bands = pack_dictionary(values, room_width)
    room_height = 2 * len(bands) + 3 + bottom_padding
    program.room(x0, y0, room_width, room_height)
    turn_x = x0 + room_width - 2

    for band_index, band in enumerate(bands):
        top_y = y0 + 1 + 2 * band_index + (1 if band_index else 0)
        bottom_y = top_y + 1
        pitch = sum(width + 3 for width in band.widths)
        final_band = band_index == len(bands) - 1
        base_x = turn_x - pitch - 1
        if band_index == 0:
            minimum_base_x = x0 + START_COLUMN + 1
        elif final_band:
            minimum_base_x = x0 + 4
        else:
            minimum_base_x = x0 + 3
        if base_x < minimum_base_x:
            raise AssertionError((base_x, x0, room_width, band))
        starts = []
        cursor = base_x
        for width in band.widths:
            starts.append(cursor)
            cursor += width + 3

        for slot, width in enumerate(band.widths):
            top_value = band.top_slots[slot]
            if top_value is not None:
                _put_row(
                    program,
                    starts[slot] + 1,
                    top_y,
                    vertical.base.p1_slot_cells(top_value, width, True),
                )
            else:
                # Keep this as a numeric literal rather than blank space.
                # Aligned backticks can also pair vertically; the zero-filled
                # partner prevents an accidental invalid vertical literal.
                _put_row(
                    program,
                    starts[slot] + 1,
                    top_y,
                    ["`", *("0" * width), "`", " "],
                )

        for slot, width in enumerate(band.widths):
            bottom_value = band.bottom_slots[slot]
            if bottom_value is not None:
                _put_row(
                    program,
                    starts[slot],
                    bottom_y,
                    vertical.base.p1_slot_cells(bottom_value, width, False),
                )
            else:
                # See the top-row case: this unsent zero is a literal syntax
                # guard, not an entry in the dictionary ring.
                _put_row(
                    program,
                    starts[slot],
                    bottom_y,
                    [" ", "`", *("0" * width), "`"],
                )

        if band_index == 0:
            program.put(x0 + START_COLUMN, top_y, "@")
        else:
            program.put(x0 + LATER_START_COLUMN, top_y, ">")
        program.put(turn_x, top_y, "v")
        program.put(turn_x, bottom_y, "<")
        if not final_band:
            program.put(
                x0 + (
                    START_COLUMN
                    if band_index == 0
                    else LATER_START_COLUMN
                ),
                bottom_y,
                "v",
            )

    # The fixed 2x4 top-left area contains the r/s pump. Constants in this
    # first band begin after it; later bands recover the horizontal space.
    for row_offset, row in enumerate(TOP_LEFT_BLOCK_ROWS):
        _put_row(program, x0 + 1, y0 + 1 + row_offset, row)

    # One dedicated row converts the first band's column-five descent into
    # the column-two starts used by every later band. Keeping this off a
    # constant row avoids forming a west/east arrow loop.
    transition_y = y0 + 3
    program.put(x0 + START_COLUMN, transition_y, "<")
    program.put(x0 + LATER_START_COLUMN, transition_y, "v")

    # After the final constant, send a zero sentinel and climb directly into
    # the pump's leading `>`, completing the loop without footer rows.
    final_bottom_y = y0 + 2 * len(bands) + 1
    program.put(x0 + 3, final_bottom_y, "0")
    program.put(x0 + 2, final_bottom_y, "s")
    for y in range(y0 + 2, final_bottom_y + 1):
        program.put(x0 + RETURN_COLUMN, y, "^")
    return room_width, room_height


def add_connection_pipes(
    program: Program,
    *,
    feeder_width: int,
    feeder_rows: int,
    dictionary: tuple[int, int, int, int],
    service_rooms: list[tuple[str, int, int, int, int]],
) -> int:
    """Connect the laid-out rooms with spacious, non-optimized pipes."""
    room_by_name = {
        name: (x, y, width, height)
        for name, x, y, width, height in service_rooms
    }
    dictionary_x, dictionary_y, dictionary_width, dictionary_height = dictionary
    decoder_x, decoder_y, decoder_width, decoder_height = room_by_name["decoder"]
    unpack_x, unpack_y, unpack_width, unpack_height = room_by_name["unpack"]
    output_x, output_y, _, output_height = room_by_name["output"]
    disp_x, disp_y, disp_width, disp_height = room_by_name["dispatcher"]

    feeder_bottom = feeder_rows + 1

    # Feeder -> DECODER: the two-row gap above the shifted service row exists
    # specifically for this short vertical connection.
    feeder_decoder_x = decoder_x + 6
    program.pipe([
        (feeder_decoder_x, feeder_bottom + 1),
        (feeder_decoder_x, decoder_y - 1),
    ])

    dictionary_bottom = dictionary_y + dictionary_height - 1

    # DECODER -> DISP, retaining the dispatcher attachment used by the
    # original vertical-P1 prototype.
    decoder_send = (decoder_x + 5, decoder_y + decoder_height)
    disp_stream_in = (
        disp_x + DISP_STREAM_IN[0],
        disp_y + DISP_STREAM_IN[1],
    )
    decoder_route_y = dictionary_bottom - 3
    program.pipe([
        decoder_send,
        (decoder_send[0], decoder_route_y),
        (disp_stream_in[0], decoder_route_y),
        disp_stream_in,
    ], end_direction="E")

    # DISP -> UNPACK, across the upper routing strip. It stays east of the
    # feeder connection, so the two pipes do not cross.
    disp_stream_out = (
        disp_x + DISP_STREAM_OUT[0],
        disp_y + DISP_STREAM_OUT[1],
    )
    unpack_stream_in = (unpack_x + 7, unpack_y - 1)
    upper_route_y = disp_y - 2
    upper_drop_x = feeder_width + 1
    program.pipe([
        disp_stream_out,
        (disp_stream_out[0], upper_route_y),
        (upper_drop_x, upper_route_y),
        (upper_drop_x, unpack_stream_in[1]),
        unpack_stream_in,
    ], end_direction="S")

    # UNPACK -> output, entering the output room from below.
    unpack_send = (unpack_x + 4, unpack_y + unpack_height)
    output_in = (output_x + 1, output_y + output_height)
    output_route_y = dictionary_bottom - 4
    program.pipe([
        unpack_send,
        (unpack_send[0], output_route_y),
        (output_in[0], output_route_y),
        output_in,
    ], end_direction="N")

    # Dictionary -> DISP and DISP -> dictionary. Attach to the dictionary's
    # right wall so neither route needs to descend below its bottom boundary.
    dictionary_ring_out = (
        dictionary_x + dictionary_width,
        dictionary_bottom - 2,
    )
    disp_ring_in = (
        disp_x + DISP_RING_IN[0],
        disp_y + DISP_RING_IN[1],
    )
    ring_forward_y = dictionary_bottom - 2
    program.pipe([
        dictionary_ring_out,
        (disp_ring_in[0], ring_forward_y),
        disp_ring_in,
    ], end_direction="N")

    disp_ring_out = (
        disp_x + DISP_RING_OUT[0],
        disp_y + DISP_RING_OUT[1],
    )
    dictionary_ring_in = (
        dictionary_x + dictionary_width,
        dictionary_bottom - 1,
    )
    ring_return_y = dictionary_bottom - 1
    program.pipe([
        disp_ring_out,
        (disp_ring_out[0], ring_return_y),
        dictionary_ring_in,
    ], end_direction="W")

    return 6


def build(
    feeder_width: int = DEFAULT_FEEDER_WIDTH,
    dictionary_width: int = DEFAULT_DICTIONARY_WIDTH,
    dictionary_words: int = DEFAULT_DICTIONARY_WORDS,
    connect_pipes: bool = False,
) -> tuple[Program, dict[str, object]]:
    if feeder_width < 8:
        raise ValueError("feeder width must be at least 8")
    if dictionary_width > feeder_width:
        raise ValueError("dictionary width cannot exceed feeder width")
    if not MIN_DICTIONARY_WORDS <= dictionary_words <= MAX_DICTIONARY_WORDS:
        raise ValueError(
            "dictionary words must be in "
            f"{MIN_DICTIONARY_WORDS}..{MAX_DICTIONARY_WORDS}"
        )

    LOGGER.info(
        "building encoding for %d dictionary words",
        dictionary_words,
    )
    symbols, ring, _ = vertical.build_encoding(
        extra_phrases=dictionary_words - MIN_DICTIONARY_WORDS,
        optimize=False,
    )
    LOGGER.info("remapping references for DP-friendly physical dictionary order")
    symbols, ring, physical_order = repack_physical_dictionary(symbols, ring)
    symbols, ring, removed_entries = remove_unused_escaped_entries(symbols, ring)
    removed_positions = {position for position, _ in removed_entries}
    physical_order = [
        old_position
        for position, old_position in enumerate(physical_order, start=1)
        if position not in removed_positions
    ]
    for position, word in removed_entries:
        LOGGER.info(
            "dropping unreferenced escaped dictionary slot %02d: %r",
            position,
            word,
        )
    usage = dictionary_usage(symbols, ring)
    LOGGER.info("selected dictionary words (physical slot: word -> references)")
    for physical_position, word, references in usage:
        LOGGER.info(
            "  %02d: %r -> %d",
            physical_position,
            word,
            references,
        )
    LOGGER.info(
        "optimizing feeder layout for width %d",
        feeder_width,
    )
    bands = vertical.base.optimize_feeder(symbols, feeder_width)
    program = Program()
    feeder_rows = vertical.base.variable_feeder(program, bands, feeder_width)
    LOGGER.info(
        "placed feeder: %d columns, %d data rows",
        feeder_width,
        feeder_rows,
    )

    tail_y = feeder_rows + 2
    dictionary_x = 0
    placed_dictionary_words = len(ring)
    dictionary_values = [
        ring[position]
        for position in range(1, placed_dictionary_words + 1)
    ]
    LOGGER.info(
        "running dictionary packing DP for width %d",
        dictionary_width,
    )
    dictionary_bands = pack_dictionary(dictionary_values, dictionary_width)
    _, dictionary_height = place_dictionary(
        program,
        dictionary_x,
        tail_y,
        dictionary_width,
        dictionary_values,
        dictionary_bands,
        bottom_padding=2 if connect_pipes else 0,
    )
    LOGGER.info(
        "placed dictionary: %d bands, %d rows",
        len(dictionary_bands),
        dictionary_height,
    )

    # Put every remaining room in one horizontal row. Connected mode moves
    # that row down two cells to open a routing strip below the feeder.
    service_y = tail_y + (2 if connect_pipes else 0)
    LOGGER.info(
        "placing horizontal service-room row%s",
        " two rows lower" if connect_pipes else "",
    )
    service_x = dictionary_width
    service_rooms = []
    for name, rows in [
        ("decoder", vertical.base.DECODER_ROWS),
        ("unpack", vertical.base.UNPACK_ROWS),
    ]:
        width = max(len(row) for row in rows) + 2
        width, height = vertical.base.paste_room(
            program, service_x, service_y, rows
        )
        service_rooms.append((name, service_x, service_y, width, height))
        service_x += width

    output_x = service_x
    program.output_room(output_x, service_y)
    service_rooms.append(("output", output_x, service_y, 3, 3))
    service_x += 3

    # DISP's compact west-wall stream input is level with the 3x3 output
    # room. Keep two routing columns between them: one for the endpoint and
    # one to stop that arrow also touching the output room's east corner.
    service_x += 2
    disp_width = max(len(row) for row in compact.DISP_ROWS) + 2
    disp_width, disp_height = vertical.base.paste_room(
        program,
        service_x,
        service_y,
        compact.DISP_ROWS,
    )
    service_rooms.append(
        ("dispatcher", service_x, service_y, disp_width, disp_height)
    )

    pipe_count = 0
    if connect_pipes:
        LOGGER.info("routing six functional connection pipes")
        pipe_count = add_connection_pipes(
            program,
            feeder_width=feeder_width,
            feeder_rows=feeder_rows,
            dictionary=(
                dictionary_x,
                tail_y,
                dictionary_width,
                dictionary_height,
            ),
            service_rooms=service_rooms,
        )
        dictionary_bottom = tail_y + dictionary_height - 1
        max_layout_y = program.bounds()[3]
        if max_layout_y > dictionary_bottom:
            raise AssertionError(
                "connected routing extends below dictionary boundary: "
                f"{max_layout_y} > {dictionary_bottom}"
            )

    LOGGER.info("validating vertical literals and layout metadata")
    bad_ticks = vertical.base.audit_vertical_ticks(program)
    if bad_ticks:
        raise AssertionError(f"vertical tick audit failed: {bad_ticks[:4]}")

    metadata = {
        "feeder_width": feeder_width,
        "feeder_rows": feeder_rows,
        "dictionary": {
            "x": dictionary_x,
            "y": tail_y,
            "width": dictionary_width,
            "height": dictionary_height,
            "bottom_padding": 2 if connect_pipes else 0,
            "requested_words": dictionary_words,
            "words": placed_dictionary_words,
            "left_edge": dictionary_x,
            "right_edge": dictionary_x + dictionary_width - 1,
            "bottom_edge": tail_y + dictionary_height - 1,
            "bands": len(dictionary_bands),
            "constants_per_band": [
                band.constant_count for band in dictionary_bands
            ],
            "slots_per_band": [
                len(band.widths) for band in dictionary_bands
            ],
            "used_width_per_band": [
                sum(width + 3 for width in band.widths)
                for band in dictionary_bands
            ],
            "physical_order": physical_order,
            "usage": [
                {
                    "position": position,
                    "word": word,
                    "references": references,
                }
                for position, word, references in usage
            ],
            "top_left_block": {
                "width": TOP_LEFT_BLOCK_WIDTH,
                "height": len(TOP_LEFT_BLOCK_ROWS),
                "rows": TOP_LEFT_BLOCK_ROWS,
                "return_column": RETURN_COLUMN,
                "start_column": START_COLUMN,
                "later_start_column": LATER_START_COLUMN,
            },
        },
        "service_rooms": service_rooms,
        "pipes": pipe_count,
        "connected": connect_pipes,
    }
    return program, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feeder-width",
        type=int,
        default=DEFAULT_FEEDER_WIDTH,
        help=f"fixed feeder width (default: {DEFAULT_FEEDER_WIDTH})",
    )
    parser.add_argument(
        "--dictionary-width",
        type=int,
        default=DEFAULT_DICTIONARY_WIDTH,
        help=(
            "fixed dictionary-room width "
            f"(default: {DEFAULT_DICTIONARY_WIDTH})"
        ),
    )
    parser.add_argument(
        "--dictionary-words",
        type=int,
        default=DEFAULT_DICTIONARY_WORDS,
        help=(
            "number of current 81x90 dictionary words to place "
            f"(default: {DEFAULT_DICTIONARY_WORDS})"
        ),
    )
    parser.add_argument(
        "--connect-pipes",
        action="store_true",
        help="move service rooms down two rows and add functional pipes",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="output .man path (default encodes the three layout parameters)",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[layout-builder] %(message)s",
    )
    args = parse_args()
    try:
        program, metadata = build(
            feeder_width=args.feeder_width,
            dictionary_width=args.dictionary_width,
            dictionary_words=args.dictionary_words,
            connect_pipes=args.connect_pipes,
        )
    except ValueError as error:
        raise SystemExit(f"error: {error}") from error

    mode_suffix = "-connected" if args.connect_pipes else ""
    output = args.output or os.path.join(
        HERE,
        (
            f"layout-f{args.feeder_width}"
            f"-d{args.dictionary_width}"
            f"-n{args.dictionary_words}"
            f"{mode_suffix}.man"
        ),
    )
    LOGGER.info("saving generated layout to %s", output)
    program.save(output)
    width, height, _ = program.footprint()
    dictionary = metadata["dictionary"]
    print(f"wrote {output}: {width}x{height}, pipes={metadata['pipes']}")
    print(
        "feeder "
        f"{args.feeder_width}x{metadata['feeder_rows'] + 2}; "
        "dictionary "
        f"{dictionary['width']}x{dictionary['height']} at "
        f"({dictionary['x']},{dictionary['y']}), "
        f"right edge={dictionary['right_edge']}; "
        f"words={dictionary['words']}; "
        f"bands={dictionary['bands']} "
        f"{dictionary['constants_per_band']}"
    )


if __name__ == "__main__":
    main()
