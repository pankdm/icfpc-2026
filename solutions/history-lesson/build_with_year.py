#!/usr/bin/env python3
"""Build the 84-wide `history-lesson` program with a stateful year decoder.

The required output is a fixed ASCII history.  Its encoded stream uses the
shifted alphabet ``symbol = ASCII - 31`` (ordinary symbols are 1..91), plus two
synthetic glyphs:

* ``13`` is the comma glyph.  Source ``, `` is encoded as only ``13``; the
  comma expander later maps it to ``13, 1`` (comma followed by shifted space).
* ``0`` is the year-boundary glyph.  Every ``"; YYYY: "`` boundary from 2000
  through 2026 is encoded as one zero.  The 1996--1999 prefixes, all colons,
  semicolons, periods, and their spaces remain ordinary shifted characters.

The feeder packs the symbols LSB-first in base 92.  Its physical decimal
literal widths are ``(18, 16, 17, 16)``; odd rows traverse those slots in
reverse order.  A zero cannot be the most-significant packed symbol because a
base-92 divmod decoder would otherwise discard it, so the packer ends a chunk
immediately before any such zero.

Pipeline:

    feeder -> base-92 decoder -> year decoder -> base-92 unpacker
           -> comma expander -> +31 restorer -> O

The first decoder turns feeder literals into shifted symbols.  The year decoder
passes every positive symbol through unchanged.  For a zero it sends the packed
base-92 spelling ``"; 2000: "`` held in B to the unpacker.  B advances by
``92**5`` (the one's-digit position in ``; YYYY: ``); BP counts ten generated
years.  At a decimal rollover it applies ``92**4 - 10*92**5`` before resetting
BP, which corrects 2009->2010 and 2019->2020.  The unpacker therefore emits the
full separator, year, colon, and space without a separate colon-space stage.

Finally, the comma expander restores omitted comma spaces and the restorer adds
31 to every shifted symbol, yielding raw ASCII at O.

Usage: python3 build_with_year.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
from littleman import Program


HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 92
OFFSET = 31
FIRST_GENERATED_YEAR = 2000
LAST_GENERATED_YEAR = 2026
PUNCT_SPACE_TOKENS = (b",",)
# 84-column feeder: the asymmetric order matters because odd feeder rows read
# physical slots in reverse.  This is the best current narrow layout.
DEFAULT_DIGIT_WIDTHS = (18, 16, 17, 16)


def packed_symbols(symbols: list[int], base: int = BASE) -> int:
    return sum(symbol * base**i for i, symbol in enumerate(symbols))


def packed_text(text: str, offset: int = OFFSET, base: int = BASE) -> int:
    return packed_symbols([ord(ch) - offset for ch in text], base)


INITIAL_YEAR_CODE = packed_text(f"; {FIRST_GENERATED_YEAR}: ")
# The changing one's digit is the sixth symbol in "; YYYY: ".
YEAR_STEP = BASE**5
# After the common step, "...9" has a digit one beyond '9'.  Move that digit
# back ten and increment the tens digit.
DECADE_CORRECTION = BASE**4 - 10 * BASE**5


def tokenize_with_year(data: bytes, offset: int = OFFSET) -> list[int]:
    """Tokenize punctuation spaces and consecutive generated year boundaries."""
    symbols: list[int] = []
    i = 0
    expected_year = FIRST_GENERATED_YEAR
    while i < len(data):
        if expected_year <= LAST_GENERATED_YEAR:
            boundary = f"; {expected_year}: ".encode("ascii")
            if data.startswith(boundary, i):
                symbols.append(0)
                i += len(boundary)
                expected_year += 1
                continue

        ch = data[i : i + 1]
        if ch in PUNCT_SPACE_TOKENS and data[i : i + 2] == ch + b" ":
            symbols.append(data[i] - offset)
            i += 2
            continue

        symbol = data[i] - offset
        if not 1 <= symbol < BASE:
            raise ValueError(f"byte {data[i]} at offset {i} is outside the source alphabet")
        symbols.append(symbol)
        i += 1

    if expected_year != LAST_GENERATED_YEAR + 1:
        raise ValueError(
            f"expected consecutive year boundaries through {LAST_GENERATED_YEAR}, "
            f"stopped before {expected_year}"
        )
    return symbols


def pack_chunks(
    symbols: list[int],
    base: int = BASE,
    maxsymbols: int = 10,
    digit_widths: tuple[int, ...] = DEFAULT_DIGIT_WIDTHS,
) -> list[int]:
    """Pack symbols LSB-first, never leaving zero as a chunk's top digit."""
    chunks: list[int] = []
    i = 0
    while i < len(symbols):
        row, slot = divmod(len(chunks), len(digit_widths))
        physical_slot = slot if row % 2 == 0 else len(digit_widths) - 1 - slot
        max_digits = digit_widths[physical_slot]
        for count in range(min(maxsymbols, len(symbols) - i), 0, -1):
            # A high zero would disappear when the decoder's quotient reaches
            # zero.  Shorten this chunk and let zero lead the next one instead.
            if symbols[i + count - 1] == 0:
                continue
            value = packed_symbols(symbols[i : i + count], base)
            if len(str(value)) <= max_digits:
                chunks.append(value)
                i += count
                break
        else:
            raise ValueError(f"cannot terminate a chunk at symbol offset {i}")
    return chunks


def put_row(program: Program, x: int, y: int, cells: list[str] | str) -> None:
    for dx, glyph in enumerate(cells):
        if glyph != " ":
            program.put(x + dx, y, glyph)


def literal_cells(value: int, direction: str = "E") -> list[str]:
    digits = str(value)
    if direction == "W":
        digits = digits[::-1]
    return ["`", *digits, "`"]


def build(
    data: bytes,
    base: int = BASE,
    maxbytes: int = 10,
    digit_widths: tuple[int, ...] = DEFAULT_DIGIT_WIDTHS,
    offset: int = OFFSET,
) -> tuple[Program, int, int]:
    """Build feeder -> decoder -> year stage -> decoder -> expanders -> output."""
    if base != BASE or offset != OFFSET or digit_widths != DEFAULT_DIGIT_WIDTHS:
        raise ValueError(
            "the folded decoder layout requires base=92, offset=31, and "
            "digit_widths=(18, 16, 17, 16)"
        )

    symbols = tokenize_with_year(data, offset)
    chunks = pack_chunks(symbols, base, maxbytes, digit_widths)
    slots = len(digit_widths)
    group_widths = [digits + 3 for digits in digit_widths]
    group_starts = [sum(group_widths[:i]) for i in range(slots)]
    program = Program()
    left = 1
    content_left = 2
    right = content_left + sum(group_widths) + 1
    rows = (len(chunks) + slots - 1) // slots

    for row in range(rows):
        y = row + 1
        east = row % 2 == 0
        for logical_slot in range(slots):
            chunk_index = row * slots + logical_slot
            if chunk_index >= len(chunks):
                break
            physical_slot = logical_slot if east else slots - 1 - logical_slot
            digits = digit_widths[physical_slot]
            decimal = str(chunks[chunk_index]).zfill(digits)
            if east:
                x = content_left + 1 + group_starts[physical_slot]
                cells = ["`", *decimal, "`", "s"]
            else:
                x = content_left + group_starts[physical_slot]
                cells = ["s", "`", *decimal[::-1], "`"]
            put_row(program, x, y, cells)
        if east:
            if row:
                program.put(left, y, ">")
            program.put(right, y, "H" if row == rows - 1 else "v")
        else:
            program.put(right, y, "<")
            program.put(left, y, "H" if row == rows - 1 else "v")
    program.put(left, 1, "@")
    feeder_bottom = rows + 1
    program.room(0, 0, right + 2, rows + 2)

    forbidden_columns = {
        x
        for y in (1, 2)
        for x in range(right + 2)
        if program.get(x, y) == "`"
    }

    def leftmost_safe_x(previous_max: int, offsets: tuple[int, ...], gap: int = 4) -> int:
        x = previous_max + gap
        while any(x + literal_offset in forbidden_columns for literal_offset in offsets):
            x += 1
        return x

    # All tail machines share this row.  The year machine is seven rows high,
    # so lift the common row six cells below the feeder.
    run_row = feeder_bottom + 6
    # The first decoder sits one row above the state loop.  This keeps its
    # bottom edge level with the year room instead of extending the footprint.
    decoder_row = run_row - 1

    def base_decoder(x0: int, row: int = run_row) -> int:
        """Place the shared 9x2 base-92 divmod loop and return its content max-x."""
        row1 = [">", "W", "/", "W", "s", "W", "X", "@", "v"]
        row2 = ["^", "`", "2", "9", "`", "M", "<", "r", "<"]
        program.room(x0, row - 1, 11, 4)
        put_row(program, x0 + 1, row, row1)
        put_row(program, x0 + 1, row + 1, row2)
        return x0 + 9

    decoder_x = leftmost_safe_x(-3, (2, 5))
    decoder_max = base_decoder(decoder_x, decoder_row)

    # Bring the feeder pipe down to the lower common row.
    feeder_pipe_x = decoder_x - 1
    program.put(feeder_pipe_x, feeder_bottom + 1, "v")
    for y in range(feeder_bottom + 2, decoder_row):
        program.put(feeder_pipe_x, y, "|")
    program.put(feeder_pipe_x, decoder_row, ">")

    # Stateful year stage, 28x7.  Its receive/control loop is on interior row 5:
    #
    #   positive symbol: N, branch north, N, s, return to r
    #   zero marker:     W s M; add YEAR_STEP; decrement decade countdown
    #                    and either return or apply DECADE_CORRECTION
    #
    # N before X makes positive inputs take X's counter-clockwise (north) path,
    # while zero continues east into the generation path.
    year_x = leftmost_safe_x(
        decoder_max,
        (
            2,
            2 + len(str(INITIAL_YEAR_CODE)) + 1,
            2 + len(str(INITIAL_YEAR_CODE)) + 3,
            7,
            7 + len(str(YEAR_STEP)) + 1,
            3,
            3 + len(str(abs(DECADE_CORRECTION))) + 1,
            3 + len(str(abs(DECADE_CORRECTION))) + 5,
        ),
    )
    year_top = run_row - 5
    program.room(year_x, year_top, 28, 7)

    # Initialization row.
    init = (
        ["@"]
        + literal_cells(INITIAL_YEAR_CODE)
        + ["M"]
        + literal_cells(10)
        + ["b", "v"]
    )
    assert len(init) == 24
    put_row(program, year_x + 1, year_top + 1, init)

    # Initialization/ordinary-symbol return lane.
    program.put(year_x + 24, year_top + 2, "<")
    program.put(year_x + 1, year_top + 2, "v")
    program.put(year_x + 23, year_top + 3, "^")
    program.put(year_x + 23, year_top + 2, "<")
    program.put(year_x + 1, year_top + 3, "v")
    program.put(year_x + 9, year_top + 3, "s")
    program.put(year_x + 9, year_top + 2, "<")

    # Receive loop and the first 18 operations of the marker path.
    loop_y = year_top + 5
    put_row(program, year_x + 1, loop_y, [">", ">", " ", " ", " ", " ", "r", "N", "X"])
    common = (
        ["W", "s", "M"]
        + literal_cells(YEAR_STEP)
        + ["+", "M", "m", "d"]
    )
    assert len(common) == 19
    put_row(program, year_x + 10, loop_y, common[:16])
    program.put(year_x + 26, loop_y, "^")
    program.put(year_x + 26, year_top + 4, "<")
    for index, glyph in enumerate(common[16:]):
        program.put(year_x + 25 - index, year_top + 4, glyph)

    # BP>0 turns north from d into the row-3 return lane.  BP==0 continues
    # west through the carry correction and resets the countdown to ten.
    carry = (
        literal_cells(abs(DECADE_CORRECTION))
        + ["N", "+", "M"]
        + literal_cells(10)
        + ["b"]
    )
    assert len(carry) == 21
    # `carry` is in execution order.  Place it right-to-left because this path
    # runs west; that also stores each literal's decimal digits reversed.
    for index, glyph in enumerate(carry):
        program.put(year_x + 22 - index, year_top + 4, glyph)
    program.put(year_x + 1, year_top + 4, "v")

    year_max = year_x + 26

    # A second base decoder is the year "unpacker".  Ordinary shifted symbols
    # are one-digit base-92 chunks and pass through unchanged.  Generated
    # boundaries already include their colon-space, so there is no colon stage.
    # Fold the remaining pipeline beside the year room.  The output room is
    # tucked beneath it, so the long final pipe does not add a feeder row.
    upper_row = feeder_bottom + 2
    unpack_x = 46
    unpack_max = base_decoder(unpack_x, upper_row)

    def expander(x0: int, token: int, row: int) -> int:
        row1 = [">", "M", "r", "s", "~", "X", "1", "s", "v"]
        row2 = ["^", "`", *str(token)[::-1], "`", "<", " ", "@", "<"]
        # Both current tokens are two decimal digits, keeping this compact form
        # aligned with the baseline builder.
        assert len(row1) == len(row2)
        program.room(x0, row - 1, 11, 4)
        put_row(program, x0 + 1, row, row1)
        put_row(program, x0 + 1, row + 1, row2)
        return x0 + 9

    comma_x = 59
    comma_max = expander(comma_x, ord(",") - offset, upper_row)

    upper_backticks = {
        unpack_x + 2,
        unpack_x + 5,
        comma_x + 2,
        comma_x + 5,
    }

    def safe_literal_x(candidates: range) -> int:
        for candidate in candidates:
            columns = {candidate + 2, candidate + 5}
            if not (columns & forbidden_columns) and not (columns & upper_backticks):
                return candidate
        raise ValueError("could not place folded tail without vertical literal pairing")

    restorer_x = safe_literal_x(range(72, 77))
    program.room(restorer_x, upper_row - 1, 9, 4)
    put_row(program, restorer_x + 1, upper_row, [">", " ", "M", "r", "+", "s", "v"])
    put_row(program, restorer_x + 1, upper_row + 1, ["^", "`", "1", "3", "`", "@", "<"])
    output_x = 45
    if output_x <= year_x + 27:
        raise ValueError("folded output room overlaps the year stage")
    program.output_room(output_x, run_row - 1)

    program.pipe(
        [
            (decoder_max + 2, decoder_row),
            (decoder_max + 3, decoder_row),
            (decoder_max + 3, run_row),
            (year_x - 1, run_row),
        ]
    )
    # State -> upper unpacker.  The state room's only `s` instructions select
    # this pipe even though it attaches above their execution rows.
    program.pipe([(year_x + 28, upper_row), (unpack_x - 1, upper_row)])
    program.pipe([(unpack_max + 2, upper_row), (comma_x - 1, upper_row)])

    program.pipe([(comma_max + 2, upper_row), (restorer_x - 1, upper_row)])
    # The restorer sends east, then the pipe loops below the tail and enters O
    # from its right side.
    program.pipe(
        [
            (restorer_x + 9, upper_row),
            (83, upper_row),
            (83, run_row),
            (output_x + 3, run_row),
        ]
    )
    return program, len(chunks), rows


def main() -> None:
    with open(os.path.join(HERE, "icfp-history.txt"), "rb") as source:
        data = source.read()
    program, chunk_count, row_count = build(data)
    output = os.path.join(HERE, "history-lesson-with-year.man")
    with open(output, "w") as destination:
        destination.write(program.render() + "\n")
    width, height, score = program.footprint()
    print(
        f"wrote {output}: {width}x{height} score={score} "
        f"chunks={chunk_count} rows={row_count}"
    )


if __name__ == "__main__":
    main()
