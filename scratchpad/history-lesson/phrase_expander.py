#!/usr/bin/env python3
"""A 'phrase expander': a full-replacement decoder stage for reserved glyphs.

Context: solutions/history-lesson/build_with_year.py encodes the source text
as base-92 packed chunks, plus two synthetic glyphs (comma=13, year-boundary
=0). This prototype adds a THIRD kind of glyph: a reserved, unused symbol
value standing in for a whole recurring phrase (e.g. " and "). Unlike the
comma glyph (which is kept in the output AND gets an extra trailing space
appended -- see build_with_year.py's `expander()`), a phrase glyph must be
FULLY REPLACED, the same way the year machine fully replaces its `0` glyph
with a packed boundary code. So on match we send ONLY the phrase's packed
literal (not the glyph); on mismatch we send ONLY the original symbol.

Placement in the pipeline: this must sit BEFORE the base-92 unpacker
(`unpack_x` in build_with_year.py), not after it like the comma expander.
The reason: on match it emits a *packed multi-symbol* literal (exactly like
the year machine's zero-glyph does), which needs the shared unpacker to turn
it back into individual symbols. Ordinary symbols and the year machine's own
already-packed boundary codes pass straight through unchanged, so chaining
   state -> phrase_expander -> unpack_x -> comma_expander -> restorer -> O
is safe: the unpacker doesn't care whether a packed value came from a year
boundary or a phrase.

Design derivation (reverse-engineered from the working comma `expander()` in
build_with_year.py, then adapted -- see conversation notes / commit message
for the full trace):

  row1 (main pass, entered facing East):
    '>'      entry / shared loop-restart landing point
    'M'      B = A            (A holds `glyph`, preloaded by the reload path)
    'r'      A = symbol       (receive)
    'W'      swap -> A=glyph, B=symbol   (preserve the original symbol!)
    '~'      A = A ^ B = glyph ^ symbol  (0 iff match; B unchanged = symbol)
    'X'      branch: match(0) -> straight (E); mismatch -> turn CW (S)
  MATCH continues east on row1:
    lit(packed_phrase)   load the phrase's packed literal
    's'                  send it (the unpacker downstream turns it back into
                          the phrase's individual symbols)
    'v'                  turn south, merge into the row2 return sweep
  MISMATCH turned south at the X cell, lands row2 at that column:
    '<'      turn west (must turn immediately -- a cell can only hold one
             instruction, so nothing else can happen at the landing cell)
    'W'      swap -> A=symbol (from B, untouched by the XOR), B=garbage
    's'      send the original symbol unchanged
    lit(glyph)   reload glyph into A for the *next* iteration's 'M'
    '^'      turn north -> lands on row1's '>' (shared restart point)
  row2 also carries the MATCH path's own return sweep (turn west after the
  'v' drop, reload glyph, merge at the SAME '^' column) and the initial
  '@' spawn, which reuses that same sweep to load glyph the very first time
  -- exactly the same trick build_with_year.py's `expander()` already uses.

This file is a standalone, interpreter-verified prototype (see __main__).
Once trusted, its `phrase_expander()` should be ported into
solutions/history-lesson/build_with_year.py as a new pipeline stage.
"""
import sys, os, subprocess

sys.path.insert(0, "/Users/pankdm/programming/icfpc-2026/tools")
from littleman import Program
from cursor import Cursor

REPO = "/Users/pankdm/programming/icfpc-2026"
BASE = 92
OFFSET = 31


def packed_symbols(symbols, base=BASE):
    return sum(s * base**i for i, s in enumerate(symbols))


def phrase_expander(p: Program, glyph: int, packed_phrase: int, x0=10, y0=10):
    """Build the room described in the module docstring. Returns
    (program, entry_x, entry_y) where entry_y is the row an incoming pipe
    should attach to (row1, the 'r' row) and entry_x is the room's own
    left-entry column (informational only -- pipes attach to the room border,
    not this interior column)."""
    y1 = y0 + 1  # main pass (match path lives here too)
    y2 = y0 + 2  # match's westbound return sweep + shared merge column + spawn
    y3 = y0 + 3  # mismatch's own extra work + its own westbound return sweep
                 # (kept OFF row2 so match's westward sweep -- which crosses
                 #  every column between x_match_turn and x_entry -- can't
                 #  trample mismatch's W/s/reload cells; see lead_expander.py
                 #  for the same conflict spelled out in more detail)

    x_entry = x0 + 1

    # --- Row1: main pass ---
    c = Cursor(p, x_entry, y1, "E")
    c.step(">")
    c.step("M")   # B = glyph
    c.step("r")   # A = symbol
    c.step("W")   # swap -> A=glyph, B=symbol (preserved)
    c.step("~")   # A = glyph ^ symbol
    c.step(".")   # filler: gives the mismatch sweep (row3) enough room
                  # between x_branch and x_entry for its W/s + reload literal
    x_branch = c.x
    c.step("X")   # match(0) -> east; mismatch -> south
    c.lit(packed_phrase)
    c.step("s")
    x_match_turn = c.x
    c.step("v")   # drop south into row2

    # --- Row2: match's westbound return sweep, reload glyph, merge at x_entry ---
    mm = Cursor(p, x_match_turn, y2, "S")
    mm.step("<")
    mm.pad_to(x_entry + len(str(glyph)) + 1)
    mm.lit(glyph)
    assert mm.x == x_entry, (mm.x, x_entry)
    mm.step("^")  # shared merge cell

    # --- Row2 pass-through + Row3: mismatch extra work + its own return sweep ---
    p.put(x_branch, y2, ".")  # no-op, continue south past match's sweep row
    m2 = Cursor(p, x_branch, y3, "S")
    m2.step("<")
    m2.step("W")
    m2.step("s")
    m2.pad_to(x_entry + len(str(glyph)) + 1)
    m2.lit(glyph)
    assert m2.x == x_entry, (m2.x, x_entry)
    m2.step("^")  # up into row2 at x_entry -- lands on mm's '^' cell (shared)

    # --- Spawn: reuse match's return sweep to load `glyph` for the first pass ---
    spawn_x = x_match_turn + 2
    p.put(spawn_x, y2, "@")
    p.put(spawn_x + 1, y2, "<")

    minx, miny, maxx, maxy = p.bounds()
    p.room(minx - 1, miny - 1, (maxx - minx + 1) + 2, (maxy - miny + 1) + 2)
    return p, x_entry, y1


def base_decoder(p: Program, x0: int, row: int) -> int:
    """The exact `base_decoder()` from build_with_year.py -- the shared
    base-92 unpacker every packed literal (year boundaries, and now phrase
    glyphs) is decoded through. Copied here (not imported) since it's defined
    as a closure inside build_with_year.py's build(); keep it byte-for-byte
    identical to that copy."""
    row1 = [">", "W", "/", "W", "s", "W", "X", "@", "v"]
    row2 = ["^", "`", "2", "9", "`", "M", "<", "r", "<"]
    p.room(x0, row - 1, 11, 4)
    for dx, g in enumerate(row1):
        if g != " ":
            p.put(x0 + 1 + dx, row, g)
    for dx, g in enumerate(row2):
        if g != " ":
            p.put(x0 + 1 + dx, row + 1, g)
    return x0 + 9


def build_test_program(glyph: int, packed_phrase: int, chain_unpacker: bool = True):
    p = Program()
    _, ex, ey = phrase_expander(p, glyph, packed_phrase, x0=2, y0=2)
    minx, miny, maxx, maxy = p.bounds()

    in_x, in_y = minx - 5, miny
    p.input_room(in_x, in_y)
    p.pipe([(in_x + 3, in_y + 1), (minx - 1, miny + 1)])

    if chain_unpacker:
        # phrase_expander -> base_decoder (unpacker) -> O, mirroring the real
        # pipeline position: state -> phrase_expander -> unpack_x -> ...
        ux = base_decoder(p, maxx + 4, miny + 1)
        p.pipe([(maxx + 1, miny + 1), (maxx + 3, miny + 1)])
        _, _, umaxx, umaxy = p.bounds()
        out_x, out_y = umaxx + 3, miny
        p.output_room(out_x, out_y)
        p.pipe([(umaxx + 1, miny + 1), (out_x - 1, out_y + 1)])
    else:
        out_x, out_y = maxx + 3, miny
        p.output_room(out_x, out_y)
        p.pipe([(maxx + 1, miny + 1), (out_x - 1, out_y + 1)])
    return p


if __name__ == "__main__":
    glyph = 2  # an unused shifted-ASCII value in icfp-history.txt (byte 33 '!')
    phrase = " and "
    packed = packed_symbols([ord(c) - OFFSET for c in phrase])
    print("packed value for", repr(phrase), "=", packed)

    p = build_test_program(glyph, packed)
    print(p.render())

    man_path = "/tmp/phrase_expander_test.man"
    with open(man_path, "w") as f:
        f.write(p.render() + "\n")

    seq = [5, glyph, 20, glyph, glyph, 3]
    in_path = "/tmp/phrase_expander_in.txt"
    with open(in_path, "w") as f:
        f.write(" ".join(map(str, seq)))
    out_path = "/tmp/phrase_expander_out.txt"

    result = subprocess.run(
        [sys.executable, "-m", "interpreter", "run", man_path, in_path, out_path,
         "--tick-limit", "20000"],
        cwd=REPO, capture_output=True, text=True,
    )
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    if os.path.exists(out_path):
        got = [int(x) for x in open(out_path).read().split()]
        expected = []
        for s in seq:
            if s == glyph:
                expected.extend(ord(c) - OFFSET for c in phrase)  # glyph FULLY replaced
            else:
                expected.append(s)
        print("input:   ", seq)
        print("expected:", expected)
        print("got:     ", got)
        print("MATCH" if got == expected else "MISMATCH")
