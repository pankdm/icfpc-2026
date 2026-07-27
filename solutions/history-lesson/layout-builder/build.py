#!/usr/bin/env python3
"""Build the raw-text dictionary layout for History Lesson.

The default output is a pipe-free geometry scaffold. Pass ``--connect-pipes``
for a runnable candidate with the compact vertical-P2 dispatcher.
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
sys.path.insert(0, HERE)
sys.path.insert(0, HISTORY_DIR)
sys.path.insert(0, TOOLS_DIR)

from littleman import Program

import build_vertical_p1 as vertical
import build_vertical_p2 as compact
import dictionary as raw_dictionary


DEFAULT_FEEDER_WIDTH = 81
DEFAULT_DICTIONARY_WIDTH = 38
DEFAULT_DICTIONARY_WORDS = 24
DICTIONARY_CATALOG = raw_dictionary.load_catalog()
MIN_DICTIONARY_WORDS = DICTIONARY_CATALOG["minimum_words"]
MAX_DICTIONARY_WORDS = DICTIONARY_CATALOG["maximum_words"]
LOGGER = logging.getLogger(__name__)
TOP_LEFT_BLOCK_ROWS = (
    ">rsv",
    "x<<<",
)
TOP_LEFT_BLOCK_WIDTH = 4
RETURN_COLUMN = 2
START_COLUMN = 5
LATER_START_COLUMN = 1

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
    # one is their start/descent and column two is the upward return.
    first_capacity = room_width - 9
    capacity = room_width - 6
    final_capacity = room_width - 10
    values_tuple = tuple(values)
    max_constants_per_band = 2 * (capacity // 4)

    @lru_cache(maxsize=None)
    def solve(index: int, first_band: bool):
        if index == len(values_tuple):
            return (0, (), 0, ())
        best = None
        remaining = len(values_tuple) - index
        for count in range(1, min(remaining, max_constants_per_band) + 1):
            segment = values_tuple[index:index + count]
            final_band = index + count == len(values_tuple)
            band_capacity = capacity
            if first_band:
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
                tail = solve(index + count, False)
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

    result = solve(0, True)
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


def _rewrite_physical_dictionary(
    symbols: list[int],
    ring: dict[int, int],
    order: list[int],
) -> tuple[list[int], dict[int, int], list[int]]:
    """Permute physical entries and rewrite every dictionary reference."""
    count = len(ring)
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


def _order_variants(
    positions: list[int],
    ring: dict[int, int],
    references: dict[int, int],
) -> list[list[int]]:
    """Small deterministic ordering portfolio for physical packing."""
    def digits(position):
        return len(str(ring[position]))

    variants = [
        list(positions),
        sorted(positions, key=lambda position: (digits(position), position)),
        sorted(positions, key=lambda position: (-digits(position), position)),
        sorted(
            positions,
            key=lambda position: (
                digits(position),
                -references[position],
                position,
            ),
        ),
        sorted(
            positions,
            key=lambda position: (
                -references[position],
                digits(position),
                position,
            ),
        ),
    ]
    by_width = sorted(positions, key=lambda position: (digits(position), position))
    alternating = []
    left = 0
    right = len(by_width) - 1
    while left <= right:
        alternating.append(by_width[right])
        right -= 1
        if left <= right:
            alternating.append(by_width[left])
            left += 1
    variants.append(alternating)

    unique = []
    seen = set()
    for variant in variants:
        key = tuple(variant)
        if key not in seen:
            seen.add(key)
            unique.append(variant)
    return unique


def repack_physical_dictionary(
    symbols: list[int],
    ring: dict[int, int],
    room_width: int,
    search_order: bool = True,
) -> tuple[list[int], dict[int, int], list[int], list[DictionaryBand]]:
    """Choose and apply the best tested physical order for paired-row packing.

    Direct and escaped positions are permuted independently so DISP's protocol
    remains unchanged. Phrase priority affects the encoded stream; this step
    affects only literal geometry.
    """
    if not search_order:
        order = list(range(1, len(ring) + 1))
        values = [ring[position] for position in order]
        bands = pack_dictionary(values, room_width)
        rewritten, new_ring, order = _rewrite_physical_dictionary(
            symbols,
            ring,
            order,
        )
        return rewritten, new_ring, order, bands

    references = {
        position: count
        for position, _, count in dictionary_usage(symbols, ring)
    }
    direct_variants = _order_variants(
        list(range(1, 17)),
        ring,
        references,
    )
    escaped_variants = _order_variants(
        list(range(17, len(ring) + 1)),
        ring,
        references,
    )

    best = None
    for direct_order in direct_variants:
        for escaped_order in escaped_variants:
            order = direct_order + escaped_order
            values = [ring[position] for position in order]
            try:
                bands = pack_dictionary(values, room_width)
            except ValueError:
                continue
            used_widths = [
                sum(width + 3 for width in band.widths)
                for band in bands
            ]
            key = (
                len(bands),
                tuple(-band.constant_count for band in bands),
                sum(used_widths),
                max(used_widths, default=0),
                tuple(order),
            )
            if best is None or key < best[0]:
                best = (key, order, bands)
    if best is None:
        raise ValueError(
            f"{len(ring)} dictionary words do not fit width {room_width}"
        )
    _, order, bands = best
    rewritten, new_ring, order = _rewrite_physical_dictionary(
        symbols,
        ring,
        order,
    )
    return rewritten, new_ring, order, bands


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
    room_height = 2 * len(bands) + 2 + bottom_padding
    program.room(x0, y0, room_width, room_height)
    turn_x = x0 + room_width - 2

    for band_index, band in enumerate(bands):
        top_y = y0 + 1 + 2 * band_index
        bottom_y = top_y + 1
        pitch = sum(width + 3 for width in band.widths)
        final_band = band_index == len(bands) - 1
        base_x = turn_x - pitch - 1
        if band_index == 0:
            minimum_base_x = x0 + START_COLUMN + 1
        elif final_band:
            # The final westbound row needs `0s1b^` before column two.
            minimum_base_x = x0 + 7
        else:
            minimum_base_x = x0 + 2
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
            # This cell is on the room edge, where `>` would become a pipe
            # endpoint and block the loader.  During preload BP=0, so `x`
            # turns a southbound man counter-clockwise to face east.
            program.put(x0 + LATER_START_COLUMN, top_y, "x")
        program.put(turn_x, top_y, "v")
        program.put(turn_x, bottom_y, "<")
        if not final_band:
            if band_index:
                program.put(x0 + LATER_START_COLUMN, bottom_y, "v")

    # The fixed 2x4 top-left area contains the r/s pump. Constants in this
    # first band begin after it; later bands recover the horizontal space.
    for row_offset, row in enumerate(TOP_LEFT_BLOCK_ROWS):
        _put_row(program, x0 + 1, y0 + 1 + row_offset, row)

    # The lower-left `x` sends BP=0 south during the one-shot preload. After
    # the final constant, emit the sentinel, set BP=1, and turn north in
    # column two.  That column is intentionally blank between bands: a
    # northbound man keeps climbing, while preload paths cross it horizontally.
    # At the pump row `<x` moves the return west, then odd BP turns it north.
    final_bottom_y = y0 + 2 * len(bands)
    program.put(x0 + 6, final_bottom_y, "0")
    program.put(x0 + 5, final_bottom_y, "s")
    program.put(x0 + 4, final_bottom_y, "1")
    program.put(x0 + 3, final_bottom_y, "b")
    program.put(x0 + RETURN_COLUMN, final_bottom_y, "^")
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
    search_dictionary_order: bool = True,
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
        "building raw-text encoding for %d dictionary words",
        dictionary_words,
    )
    symbols, ring, selection = raw_dictionary.build_encoding(
        vertical.base.TEXT,
        dictionary_words,
    )
    LOGGER.info(
        "dictionary choice order "
        "(semantic slot: word, residual occurrences -> final references)"
    )
    for action in selection["actions"]:
        slot = action["slot"]
        occurrences = action.get("occurrences_at_selection")
        occurrence_label = (
            str(occurrences)
            if occurrences is not None
            else "required identity"
        )
        LOGGER.info(
            "  %02d: %r [%s], %s -> %d",
            slot,
            action["word"],
            action["kind"],
            occurrence_label,
            selection["references"][slot],
        )
    if search_dictionary_order:
        LOGGER.info(
            "selecting physical order for width %d while preserving reference class",
            dictionary_width,
        )
    else:
        LOGGER.info("keeping catalog dictionary order (ordering search disabled)")
    symbols, ring, physical_order, dictionary_bands = (
        repack_physical_dictionary(
            symbols,
            ring,
            dictionary_width,
            search_order=search_dictionary_order,
        )
    )
    usage = dictionary_usage(symbols, ring)
    LOGGER.info(
        "physical packing order after reference rewrite "
        "(physical slot: word -> references)"
    )
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
    unpadded_dictionary_height = 2 * len(dictionary_bands) + 2
    # Connected mode needs the dictionary's bottom boundary to cover DISP's
    # south-wall ring endpoints. Small dictionaries can be shorter than that
    # service tail, so two fixed footer rows are not always sufficient.
    dictionary_bottom_padding = (
        max(
            2,
            # Two rows from dictionary top to service top, then DISP's south
            # port offset, then two distinct route rows before the dictionary
            # bottom corner.
            2 + (len(compact.DISP_ROWS) + 2) + 2 - (
                unpadded_dictionary_height - 1
            ),
        )
        if connect_pipes
        else 0
    )
    _, dictionary_height = place_dictionary(
        program,
        dictionary_x,
        tail_y,
        dictionary_width,
        dictionary_values,
        dictionary_bands,
        bottom_padding=dictionary_bottom_padding,
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
            "bottom_padding": dictionary_bottom_padding,
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
            "selection_actions": selection["actions"],
            "selection_encoding": selection["catalog"]["encoding"],
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
        "searched_dictionary_order": search_dictionary_order,
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
            f"raw-text dictionary budget ({MIN_DICTIONARY_WORDS}.."
            f"{MAX_DICTIONARY_WORDS}) "
            f"(default: {DEFAULT_DICTIONARY_WORDS})"
        ),
    )
    parser.add_argument(
        "--connect-pipes",
        action="store_true",
        help="move service rooms down two rows and add functional pipes",
    )
    parser.add_argument(
        "--no-order-search",
        action="store_true",
        help=(
            "keep catalog dictionary order instead of auditing physical "
            "permutations (faster, potentially larger)"
        ),
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
            search_dictionary_order=not args.no_order_search,
        )
    except ValueError as error:
        raise SystemExit(f"error: {error}") from error

    mode_suffix = "-connected" if args.connect_pipes else ""
    order_suffix = "-natural-order" if args.no_order_search else ""
    output = args.output or os.path.join(
        HERE,
        (
            f"layout-f{args.feeder_width}"
            f"-d{args.dictionary_width}"
            f"-n{args.dictionary_words}"
            f"{order_suffix}"
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
