#!/usr/bin/env python3
"""Build a working, deliberately oversized version of the 80x80 scaffold.

This keeps the 80-column feeder and 55-column/52-word dictionary from the
folded layout, but uses the proven vertical-P2 dispatcher and the original
base-92 stream protocol.  Pipes are routed outside the target square on
purpose: this artifact is a correctness baseline for subsequent compaction.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.dirname(HERE)
TOOLS_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "..", "tools"))
sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, HISTORY_DIR)
sys.path.insert(0, HERE)

from littleman import Program

import build as layout
import build_vertical_p2 as p2
import dictionary as raw_dictionary


FEEDER_WIDTH = 80
DICTIONARY_WIDTH = 55
DICTIONARY_WORDS = 52
DISPATCHER_X = 56

# The original decoder, folded from 9x2 to 8x3.  ``29`` is read westward as
# 92, just as ``46`` is read as 64 in the compact-alphabet experiment.
FOLDED_DECODER92_ROWS = (
    ">W/WsWXU",
    "^`29`M<<",
    "@r     ^",
)


def _pipe(
    program: Program,
    points: list[tuple[int, int]],
    *,
    end_direction: str | None = None,
) -> None:
    """Place a prototype pipe, rejecting accidental room/code overwrites."""
    before = dict(program.cells)
    program.pipe(points, end_direction=end_direction)
    for position, old_glyph in before.items():
        new_glyph = program.cells.get(position)
        if old_glyph != " " and new_glyph != old_glyph:
            raise AssertionError(
                f"pipe overwrote {old_glyph!r} at {position} with {new_glyph!r}"
            )


def build() -> tuple[Program, dict[str, object]]:
    catalog_path = os.path.join(HERE, "dictionary_words_layout_gain.json")
    catalog = raw_dictionary.load_catalog(catalog_path)
    symbols, ring, selection = raw_dictionary.build_encoding(
        p2.base.TEXT,
        DICTIONARY_WORDS,
        catalog,
    )
    symbols, ring, physical_order, dictionary_bands = (
        layout.repack_physical_dictionary(
            symbols,
            ring,
            DICTIONARY_WIDTH,
            search_order=True,
            preload_bp2=False,
        )
    )

    feeder_bands = p2.base.optimize_feeder(
        symbols,
        FEEDER_WIDTH,
        base=p2.base.B1,
    )
    program = Program()
    feeder_rows = p2.base.variable_feeder(
        program,
        feeder_bands,
        FEEDER_WIDTH,
    )

    # Four empty rows below the feeder make the borrowed room's ports easy to
    # audit.  Compaction starts only after this version passes end to end.
    tail_y = feeder_rows + 6
    values = [ring[position] for position in range(1, len(ring) + 1)]
    _, dictionary_height = layout.place_dictionary(
        program,
        0,
        tail_y,
        DICTIONARY_WIDTH,
        values,
        dictionary_bands,
        preload_bp2=False,
    )

    dispatcher_y = tail_y
    dispatcher_width, dispatcher_height = p2.base.paste_room(
        program,
        DISPATCHER_X,
        dispatcher_y,
        p2.DISP_ROWS,
    )

    # Keep P2 in the exact former @H position.  Put the small codec rooms in a
    # spacious east-side stack for the correctness baseline; only these rooms
    # and their pipes overflow the intended square.
    decoder_x = 80
    decoder_y = tail_y
    unpack_x = 78
    unpack_y = tail_y + 8
    output_x = 85
    output_y = tail_y + 14
    unpack_width, unpack_height = p2.base.paste_room(
        program,
        unpack_x,
        unpack_y,
        p2.base.UNPACK_ROWS,
    )
    decoder_width, decoder_height = p2.base.paste_room(
        program,
        decoder_x,
        decoder_y,
        FOLDED_DECODER92_ROWS,
    )
    program.output_room(output_x, output_y)

    dictionary_bottom = tail_y + dictionary_height - 1

    # Feeder -> base-92 decoder, around the east side.
    _pipe(program, [
        (FEEDER_WIDTH, feeder_rows),
        (decoder_x + decoder_width - 2, feeder_rows),
        (decoder_x + decoder_width - 2, decoder_y - 1),
    ], end_direction="S")

    # Decoder -> P2 stream input through the upper blank row.
    stream_in = (
        DISPATCHER_X + layout.DISP_STREAM_IN[0],
        dispatcher_y + layout.DISP_STREAM_IN[1],
    )
    _pipe(program, [
        (decoder_x + 5, decoder_y - 1),
        (decoder_x + 5, dispatcher_y - 3),
        (stream_in[0], dispatcher_y - 3),
        stream_in,
    ], end_direction="E")

    # P2 -> /128 unpacker down the stack's west side.
    dispatcher_unpack = (
        DISPATCHER_X + layout.DISP_STREAM_OUT[0],
        dispatcher_y + layout.DISP_STREAM_OUT[1],
    )
    _pipe(program, [
        dispatcher_unpack,
        (dispatcher_unpack[0], dispatcher_y - 2),
        (unpack_x + 1, dispatcher_y - 2),
        (unpack_x + 1, unpack_y - 1),
        (unpack_x + unpack_width - 2, unpack_y - 1),
    ], end_direction="S")

    # /128 unpacker -> output, a two-cell vertical pipe.
    _pipe(program, [
        (unpack_x + 8, unpack_y + unpack_height),
        (unpack_x + 8, output_y - 1),
    ], end_direction="S")

    # Dictionary -> P2 ring input.  Both ring legs use exact P2 attachment
    # coordinates, preserving the nearest-pipe choices inside the dispatcher.
    dispatcher_ring_in = (
        DISPATCHER_X + layout.DISP_RING_IN[0],
        dispatcher_y + layout.DISP_RING_IN[1],
    )
    _pipe(program, [
        (DICTIONARY_WIDTH, dispatcher_y + 7),
        (73, dispatcher_y + 7),
        (73, dispatcher_y + 9),
        (55, dispatcher_y + 9),
        (55, dispatcher_y + 11),
        (73, dispatcher_y + 11),
        (73, dispatcher_y + 13),
        (55, dispatcher_y + 13),
        (55, dispatcher_y + 15),
        (75, dispatcher_y + 15),
        (75, dispatcher_y + 8),
        (dispatcher_ring_in[0], dispatcher_y + 8),
        dispatcher_ring_in,
    ], end_direction="N")

    # P2 -> dictionary ring input in the next row.
    dispatcher_ring_out = (
        DISPATCHER_X + layout.DISP_RING_OUT[0],
        dispatcher_y + layout.DISP_RING_OUT[1],
    )
    _pipe(program, [
        dispatcher_ring_out,
        (dispatcher_ring_out[0], dictionary_bottom + 1),
        (50, dictionary_bottom + 1),
    ], end_direction="N")

    bad_ticks = p2.base.audit_vertical_ticks(program)
    if bad_ticks:
        raise AssertionError(f"vertical tick audit failed: {bad_ticks[:4]}")

    usage = layout.dictionary_usage(symbols, ring)
    return program, {
        "catalog": catalog_path,
        "selection": selection,
        "physical_order": physical_order,
        "usage": usage,
        "feeder_rows": feeder_rows,
        "tail_y": tail_y,
        "dictionary_bands": len(dictionary_bands),
        "dictionary_height": dictionary_height,
        "dispatcher": (
            DISPATCHER_X,
            dispatcher_y,
            dispatcher_width,
            dispatcher_height,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(
            HISTORY_DIR,
            "candidates",
            "90x90-folded-p2-working-prototype.man",
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    program, metadata = build()
    program.save(args.output)
    width, height, score = program.footprint()
    print(
        f"wrote {args.output}: {width}x{height} box={score}; "
        f"feeder=80x{metadata['feeder_rows'] + 2}; "
        f"dictionary=55x{metadata['dictionary_height']} "
        f"({metadata['dictionary_bands']} bands)"
    )


if __name__ == "__main__":
    main()
