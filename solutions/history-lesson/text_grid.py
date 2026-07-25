#!/usr/bin/env python3
"""Explore text-token glyphs and the dense feeder grid for History Lesson.

The generated program stores its input as base-92 integers in a boustrophedon
feeder.  A *special glyph* is one decoded symbol that expands back into a
longer piece of text.  The current program uses these two safe substitutions:

    ", "  ->  ","
    ": "  ->  ":"

This tool does not change ``history-lesson-v3.man``.  It answers the useful
first question for a proposed compression: how small can its input feeder be
with the existing literal/chunk encoding?  Add phrases on the command line:

    python3 text_grid.py --add ' and '

or add ``Glyph(' and ')`` to ``EXTRA_GLYPHS`` below.  An added phrase receives
an unused printable marker automatically; use ``Glyph(' and ', '~')`` to pin
one.  The marker must not occur anywhere that is not replaced by a mapping.

The layout search uses the same greedy chunk rule as build.py.  It searches all
physical slot-width lists with up to five slots that could beat the current
85-cell feeder, including every slot order because odd feeder rows run in
reverse.
"""
from __future__ import annotations

import argparse
import itertools
import os
from dataclasses import dataclass


HERE = os.path.dirname(os.path.abspath(__file__))
PROPOSED_GRID_PATH = os.path.join(HERE, "proposed-input-grid.txt")
OFFSET = 31
BASE = 92
MAX_DIGITS = 18       # Every <=18-digit literal and its decimal reverse fit i64.
MAX_SYMBOLS = 10      # Kept in lock-step with build.py's current decoder feeder.
FEEDER_EXTRA_ROWS = 4 # Decoder/footer rows below the standalone feeder grid.


@dataclass(frozen=True)
class Glyph:
    """Map ``text`` to one base-92 symbol; ``marker=None`` chooses one safely."""
    text: str
    marker: str | None = None


# Edit this list for repeatable experiments.  The two fixed mappings are the
# expanders already implemented by build.py; extras are planning-only until an
# expander for them is added to the builder.
SPECIAL_GLYPHS = [
    Glyph(", ", ","),
    Glyph(": ", ":"),
]
EXTRA_GLYPHS: list[Glyph] = []


def as_bytes(value: str, what: str) -> bytes:
    try:
        result = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError(f"{what} must be ASCII: {value!r}") from error
    if not result:
        raise ValueError(f"{what} cannot be empty")
    return result


def _matches(data: bytes, phrases: list[bytes]):
    """Yield (start, phrase-index), choosing the longest phrase at each byte."""
    i = 0
    order = sorted(range(len(phrases)), key=lambda n: (-len(phrases[n]), n))
    while i < len(data):
        hit = next((n for n in order if data.startswith(phrases[n], i)), None)
        if hit is None:
            yield i, None
            i += 1
        else:
            yield i, hit
            i += len(phrases[hit])


def resolve_glyphs(data: bytes, glyphs: list[Glyph]) -> list[tuple[bytes, int]]:
    """Validate mappings and turn their marker characters into shifted symbols."""
    phrases = [as_bytes(g.text, "glyph text") for g in glyphs]
    if len(set(phrases)) != len(phrases):
        raise ValueError("each glyph text must be unique")

    # First find source bytes which will remain literal.  An automatic marker may
    # reuse only a character absent from this stream, just like comma and colon.
    literal = bytearray()
    for pos, hit in _matches(data, phrases):
        if hit is None:
            literal.append(data[pos])
    literal_set = set(literal)

    markers: list[int | None] = []
    for g in glyphs:
        if g.marker is None:
            markers.append(None)
            continue
        marker = as_bytes(g.marker, "glyph marker")
        if len(marker) != 1 or not 32 <= marker[0] <= 122:
            raise ValueError("glyph marker must be one printable byte in ASCII 32..122")
        markers.append(marker[0])

    claimed = {m for m in markers if m is not None}
    if len(claimed) != len([m for m in markers if m is not None]):
        raise ValueError("each glyph must use a different marker")
    for i, marker in enumerate(markers):
        if marker is not None:
            if marker in literal_set:
                raise ValueError(
                    f"marker {chr(marker)!r} for {glyphs[i].text!r} also occurs as literal text")
            continue
        marker = next((b for b in range(32, 123) if b not in literal_set and b not in claimed), None)
        if marker is None:
            raise ValueError(f"no unused marker is available for {glyphs[i].text!r}")
        markers[i] = marker
        claimed.add(marker)

    return [(phrases[i], markers[i] - OFFSET) for i in range(len(glyphs))]


def tokenize(data: bytes, mappings: list[tuple[bytes, int]]) -> tuple[list[int], list[int]]:
    """Return shifted symbols plus the occurrence count for every special glyph."""
    phrases = [phrase for phrase, _ in mappings]
    symbols: list[int] = []
    counts = [0] * len(mappings)
    for pos, hit in _matches(data, phrases):
        if hit is None:
            symbol = data[pos] - OFFSET
            if not 1 <= symbol < BASE:
                raise ValueError(f"byte {data[pos]} is outside the base-92 source alphabet")
            symbols.append(symbol)
        else:
            symbols.append(mappings[hit][1])
            counts[hit] += 1
    return symbols, counts


def take_table(symbols: list[int]) -> list[list[int]]:
    """Maximum greedy chunk length at each text position for every digit width."""
    table = [[0] * (MAX_DIGITS + 1) for _ in symbols]
    for i in range(len(symbols)):
        value = 0
        power = 1
        for n in range(1, min(MAX_SYMBOLS, len(symbols) - i) + 1):
            value += symbols[i + n - 1] * power
            power *= BASE
            digits = len(str(value))
            if digits > MAX_DIGITS:
                break
            for width in range(digits, MAX_DIGITS + 1):
                table[i][width] = n
    return table


def pack_count(table: list[list[int]], widths: tuple[int, ...]) -> int:
    """Count chunks using build.py's greedy packing and row-direction slot order."""
    i = chunks = 0
    slots = len(widths)
    while i < len(table):
        row, slot = divmod(chunks, slots)
        width = widths[slot if row % 2 == 0 else slots - 1 - slot]
        n = table[i][width]
        if not n:
            raise AssertionError(f"{width}-digit slot cannot encode symbol {i}")
        i += n
        chunks += 1
    return chunks


def pack_chunks(symbols: list[int], widths: tuple[int, ...]) -> list[int]:
    """Return the integer literals for a layout, using the builder's greedy rule."""
    table = take_table(symbols)
    chunks: list[int] = []
    i = 0
    slots = len(widths)
    while i < len(symbols):
        row, slot = divmod(len(chunks), slots)
        width = widths[slot if row % 2 == 0 else slots - 1 - slot]
        n = table[i][width]
        value = sum(symbols[i + j] * (BASE ** j) for j in range(n))
        chunks.append(value)
        i += n
    return chunks


@dataclass(frozen=True)
class Layout:
    widths: tuple[int, ...]
    chunks: int
    extra_rows: int = FEEDER_EXTRA_ROWS

    @property
    def grid_width(self) -> int:
        # Each slot is ` + decimal digits + ` + s; feeder walls add five cells.
        return sum(d + 3 for d in self.widths) + 5

    @property
    def rows(self) -> int:
        return (self.chunks + len(self.widths) - 1) // len(self.widths)

    @property
    def grid_height(self) -> int:
        # One top and one bottom feeder wall.
        return self.rows + 2

    @property
    def planned_height(self) -> int:
        """Full layout height after reserving the feeder's decoder/footer rows."""
        return self.grid_height + self.extra_rows

    @property
    def side(self) -> int:
        return max(self.grid_width, self.planned_height)


def render_feeder(symbols: list[int], layout: Layout) -> str:
    """Render the standalone feeder grid that would hold this encoded text.

    This is the input room from build.py generalized to the selected slot widths.
    It is executable as a feeder: literals are sent in FIFO order and the runner
    halts cleanly at the final row.  The decoder/expanders are intentionally not
    included, because this tool is comparing only the proposed input grid.
    """
    chunks = pack_chunks(symbols, layout.widths)
    slot_widths = [d + 3 for d in layout.widths]
    starts = [sum(slot_widths[:i]) for i in range(len(slot_widths))]
    width, height = layout.grid_width, layout.grid_height
    cells = [[" "] * width for _ in range(height)]

    def put(x: int, y: int, glyph: str) -> None:
        cells[y][x] = glyph

    # Feeder walls.  Interior is x=1..width-2, y=1..height-2.
    for x in range(width):
        put(x, 0, "-")
        put(x, height - 1, "-")
    for y in range(height):
        put(0, y, "|")
        put(width - 1, y, "|")
    for x, y in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        put(x, y, "+")

    slots = len(layout.widths)
    exit_col = width - 2
    for row in range(layout.rows):
        y = row + 1
        east = row % 2 == 0
        for logical_slot in range(slots):
            chunk_index = row * slots + logical_slot
            if chunk_index >= len(chunks):
                break
            physical_slot = logical_slot if east else slots - 1 - logical_slot
            digits = layout.widths[physical_slot]
            literal = str(chunks[chunk_index]).zfill(digits)
            if east:
                x = 3 + starts[physical_slot]
                glyphs = "`" + literal + "`s"
            else:
                x = 2 + starts[physical_slot]
                glyphs = "s`" + literal[::-1] + "`"
            for offset, glyph in enumerate(glyphs):
                put(x + offset, y, glyph)
        if east:
            if row:
                put(1, y, ">")
            put(exit_col, y, "H" if row == layout.rows - 1 else "v")
        else:
            put(exit_col, y, "<")
            put(1, y, "H" if row == layout.rows - 1 else "v")
    put(1, 1, "@")
    return "\n".join("".join(row) for row in cells)


def layout_key(layout: Layout) -> tuple[int, int, int, tuple[int, ...]]:
    """Rank square size first, then footprint, packing density, and determinism."""
    return (layout.side, layout.grid_width * layout.planned_height, layout.chunks, layout.widths)


def ranked_layouts(
    symbols: list[int],
    max_slots: int = 5,
    extra_rows: int = FEEDER_EXTRA_ROWS,
    side_slack: int = 2,
) -> list[Layout]:
    """Return the best order for each near-optimal physical width configuration."""
    table = take_table(symbols)
    # The checked-in layout is a valid, useful upper bound.  It also keeps this
    # exhaustive search compact: wider layouts cannot improve the feeder side.
    baseline_side = Layout((16, 16, 18, 18), pack_count(table, (16, 16, 18, 18)), extra_rows).side
    side_limit = baseline_side + side_slack
    # For a given digit width, no slot can consume more than this many symbols at
    # any source offset.  Summing these maxima gives a safe, tight row-capacity
    # bound before trying each order's actual greedy pack.
    max_take = [0] + [max(row[digits] for row in table) for digits in range(1, MAX_DIGITS + 1)]
    best_by_widths: dict[tuple[int, ...], Layout] = {}
    for slots in range(1, max_slots + 1):
        for widths in itertools.combinations_with_replacement(range(1, MAX_DIGITS + 1), slots):
            feeder_width = sum(d + 3 for d in widths) + 5
            if feeder_width > side_limit:
                continue
            # Even a stream of maximally packable chunks would need too many rows.
            capacity = sum(max_take[d] for d in widths)
            if capacity == 0:
                continue
            if (len(symbols) + capacity - 1) // capacity + 2 + extra_rows > side_limit:
                continue
            # A physical slot list is read forward then backward.  Width order can
            # change a few boundary chunks, so check every distinct order here.
            for widths in set(itertools.permutations(widths)):
                try:
                    layout = Layout(widths, pack_count(table, widths), extra_rows)
                except AssertionError:
                    # A narrow slot can only encode a subset of symbols; another
                    # ordering (or width list) may still be usable.
                    continue
                if layout.side > side_limit:
                    continue
                physical_widths = tuple(sorted(widths))
                old = best_by_widths.get(physical_widths)
                if old is None or layout_key(layout) < layout_key(old):
                    best_by_widths[physical_widths] = layout
    if not best_by_widths:
        raise AssertionError("the baseline feeder layout must be a candidate")
    return sorted(best_by_widths.values(), key=layout_key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text", default=os.path.join(HERE, "icfp-history.txt"), help="ASCII text to analyze")
    parser.add_argument("--add", action="append", default=[], metavar="TEXT", help="add an auto-marked special glyph")
    parser.add_argument("--no-defaults", action="store_true", help="do not include the comma-space and colon-space glyphs")
    parser.add_argument("--max-slots", type=int, default=5, help="search up to this many feeder slots (default: 5)")
    parser.add_argument("--feeder-extra-rows", type=int, default=FEEDER_EXTRA_ROWS,
                        help=f"rows reserved below the feeder (default: {FEEDER_EXTRA_ROWS})")
    parser.add_argument("--top", type=int, default=5, help="number of ranked physical configurations to show (default: 5)")
    parser.add_argument("--side-slack", type=int, default=2,
                        help="also search configurations up to this many cells above the baseline side (default: 2)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.max_slots <= 7:
        raise SystemExit("--max-slots must be between 1 and 7")
    if args.feeder_extra_rows < 0:
        raise SystemExit("--feeder-extra-rows must be non-negative")
    if args.top < 1:
        raise SystemExit("--top must be positive")
    if args.side_slack < 0:
        raise SystemExit("--side-slack must be non-negative")
    data = open(args.text, "rb").read()
    glyphs = ([] if args.no_defaults else SPECIAL_GLYPHS) + EXTRA_GLYPHS + [Glyph(text) for text in args.add]
    try:
        mappings = resolve_glyphs(data, glyphs)
        symbols, counts = tokenize(data, mappings)
    except ValueError as error:
        raise SystemExit(f"mapping error: {error}") from error

    layouts = ranked_layouts(symbols, args.max_slots, args.feeder_extra_rows, args.side_slack)
    layout = layouts[0]
    print(f"text: {len(data)} bytes -> {len(symbols)} encoded symbols ({len(data) - len(symbols)} saved)")
    print("special glyphs:")
    for glyph, (_, symbol), count in zip(glyphs, mappings, counts):
        print(f"  {glyph.text!r:28} -> {chr(symbol + OFFSET)!r:4}  symbol={symbol:2}  uses={count}")
    print(f"best square-aware layout: {layout.grid_width}x{layout.planned_height}  side={layout.side}")
    print(f"  feeder grid={layout.grid_width}x{layout.grid_height} (+{layout.extra_rows} reserved rows)")
    print(f"  slots={len(layout.widths)} widths={list(layout.widths)} chunks={layout.chunks} rows={layout.rows}")
    if args.top > 1:
        print(f"top configurations (within side {layout.side + args.side_slack}):")
        for rank, candidate in enumerate(layouts[:args.top], 1):
            physical_widths = list(sorted(candidate.widths))
            print(
                f"  {rank:2}. side={candidate.side:2} planned={candidate.grid_width}x{candidate.planned_height} "
                f"feeder={candidate.grid_width}x{candidate.grid_height} chunks={candidate.chunks:3} "
                f"widths={physical_widths} order={list(candidate.widths)}"
            )
    with open(PROPOSED_GRID_PATH, "w") as output:
        output.write(render_feeder(symbols, layout) + "\n")
    print(f"wrote proposed feeder grid: {PROPOSED_GRID_PATH}")


if __name__ == "__main__":
    main()
