#!/usr/bin/env python3
"""Build a pipe-free layout scaffold for the vertical-P1 History Lesson design.

This is intentionally not a candidate solution yet.  It places the optimized
feeder, a fixed-width vertical dictionary, and the remaining rooms, but draws
no pipes between them.  The scaffold is useful for experimenting with the
feeder/dictionary geometry before committing to pipe attachment locations.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.dirname(HERE)
TOOLS_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "..", "tools"))
sys.path.insert(0, HISTORY_DIR)
sys.path.insert(0, TOOLS_DIR)

from littleman import Program

import build_vertical_p1 as vertical


DEFAULT_FEEDER_WIDTH = 81
DEFAULT_DICTIONARY_WIDTH = 52
DEFAULT_DICTIONARY_WORDS = 44
MIN_DICTIONARY_WORDS = 38
MAX_DICTIONARY_WORDS = 91
ROOM_GAP = 1


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


def _best_band(values: tuple[int, ...], top_count: int) -> DictionaryBand:
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
    if room_width < 8:
        raise ValueError("dictionary width must be at least 8")
    capacity = room_width - 5
    final_capacity = room_width - 7
    values_tuple = tuple(values)
    max_constants_per_band = 2 * (capacity // 4)

    @lru_cache(maxsize=None)
    def solve(index: int):
        if index == len(values_tuple):
            return (0, (), 0, ())
        best = None
        remaining = len(values_tuple) - index
        for count in range(1, min(remaining, max_constants_per_band) + 1):
            segment = values_tuple[index:index + count]
            band_capacity = (
                final_capacity if index + count == len(values_tuple)
                else capacity
            )
            for top_count in range(1, count + 1):
                band = _best_band(segment, top_count)
                used = sum(width + 3 for width in band.widths)
                if used > band_capacity:
                    continue
                tail = solve(index + count)
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

    result = solve(0)
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


def right_aligned_after(
    feeder_width: int,
    room_width: int,
    occupied_left_width: int,
) -> int:
    """Right-align a room unless that would overlap the left-side block.

    When the two widths do not fit inside the feeder boundary, the room
    touches the left block at its next free column and is allowed to extend
    past the feeder's right edge.
    """
    return max(feeder_width - room_width, occupied_left_width)


def place_dictionary(
    program: Program,
    x0: int,
    y0: int,
    room_width: int,
    values: list[int],
) -> tuple[int, int]:
    """Place a right-aligned vertical-P1 dictionary and return (width, height)."""
    bands = pack_dictionary(values, room_width)
    room_height = 2 * len(bands) + 4
    program.room(x0, y0, room_width, room_height)
    turn_x = x0 + room_width - 2

    for band_index, band in enumerate(bands):
        top_y = y0 + 1 + 2 * band_index
        bottom_y = top_y + 1
        pitch = sum(width + 3 for width in band.widths)
        # The final eastbound send ends one cell before the turn.  Computing
        # starts from that edge makes every band right-aligned despite having
        # a different set of slot widths.
        base_x = turn_x - pitch - 1
        if base_x < x0 + 2:
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
                _put_row(
                    program,
                    starts[slot],
                    bottom_y,
                    [" ", "`", *("0" * width), "`"],
                )

        program.put(x0 + 1, top_y, "@" if band_index == 0 else ">")
        program.put(turn_x, top_y, "v")
        program.put(turn_x, bottom_y, "<")
        program.put(x0 + 1, bottom_y, "v")

    # Keep the buffer loop strictly after the preload.  On the last westbound
    # row the loader encounters the zero sentinel only after all constants,
    # then descends directly into the steady r/s iteration loop.
    final_bottom_y = y0 + 2 * len(bands)
    program.put(x0 + 3, final_bottom_y, "0")
    program.put(x0 + 2, final_bottom_y, "s")
    pump_y = final_bottom_y + 1
    _put_row(
        program,
        x0 + 1,
        pump_y,
        [">", ">", "r", "s", "v"],
    )
    _put_row(
        program,
        x0 + 1,
        pump_y + 1,
        [" ", "^", "<", "<", "<"],
    )
    return room_width, room_height


def build(
    feeder_width: int = DEFAULT_FEEDER_WIDTH,
    dictionary_width: int = DEFAULT_DICTIONARY_WIDTH,
    dictionary_words: int = DEFAULT_DICTIONARY_WORDS,
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

    symbols, ring, candidate_bands = vertical.build_encoding(
        extra_phrases=dictionary_words - MIN_DICTIONARY_WORDS
    )
    bands = (
        candidate_bands
        if feeder_width == vertical.WIDTH
        else vertical.base.optimize_feeder(symbols, feeder_width)
    )
    program = Program()
    feeder_rows = vertical.base.variable_feeder(program, bands, feeder_width)

    tail_y = feeder_rows + 2
    dictionary_x = 0
    dictionary_values = [ring[position] for position in range(1, dictionary_words + 1)]
    dictionary_bands = pack_dictionary(dictionary_values, dictionary_width)
    _, dictionary_height = place_dictionary(
        program,
        dictionary_x,
        tail_y,
        dictionary_width,
        dictionary_values,
    )

    # Stack the remaining rooms down the feeder's right boundary. If a room
    # cannot fit between the dictionary and that boundary, put it immediately
    # after the dictionary and let it extend rightward. This makes overlap
    # impossible for every supported dictionary width.
    service_y = tail_y
    service_rooms = []
    for name, rows in [
        ("decoder", vertical.base.DECODER_ROWS),
        ("unpack", vertical.base.UNPACK_ROWS),
    ]:
        width = max(len(row) for row in rows) + 2
        service_x = right_aligned_after(
            feeder_width, width, dictionary_width
        )
        width, height = vertical.base.paste_room(
            program, service_x, service_y, rows
        )
        service_rooms.append((name, service_x, service_y, width, height))
        service_y += height + ROOM_GAP

    output_x = right_aligned_after(feeder_width, 3, dictionary_width)
    program.output_room(output_x, service_y)
    service_rooms.append(("output", output_x, service_y, 3, 3))
    service_y += 3 + ROOM_GAP

    disp_width = max(len(row) for row in vertical.DISP_DELAYED_ROWS) + 2
    service_x = right_aligned_after(
        feeder_width, disp_width, dictionary_width
    )
    disp_width, disp_height = vertical.base.paste_room(
        program,
        service_x,
        service_y,
        vertical.DISP_DELAYED_ROWS,
    )
    service_rooms.append(
        ("dispatcher", service_x, service_y, disp_width, disp_height)
    )

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
            "words": dictionary_words,
            "left_edge": dictionary_x,
            "right_edge": dictionary_x + dictionary_width - 1,
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
        },
        "service_rooms": service_rooms,
        "pipes": 0,
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
        "-o",
        "--output",
        help="output .man path (default encodes the three layout parameters)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        program, metadata = build(
            feeder_width=args.feeder_width,
            dictionary_width=args.dictionary_width,
            dictionary_words=args.dictionary_words,
        )
    except ValueError as error:
        raise SystemExit(f"error: {error}") from error

    output = args.output or os.path.join(
        HERE,
        (
            f"layout-f{args.feeder_width}"
            f"-d{args.dictionary_width}"
            f"-n{args.dictionary_words}.man"
        ),
    )
    program.save(output)
    width, height, _ = program.footprint()
    dictionary = metadata["dictionary"]
    print(f"wrote {output}: {width}x{height}, pipes=0")
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
