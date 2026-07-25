#!/usr/bin/env python3
"""phrase_expander v2 -- a 2-content-row (4-tall) phrase expander.

v1 (phrase_expander.py) needed THREE content rows because the match and
mismatch paths each carried their own `s` (send) and their own westbound
reload sweep, and those sweeps couldn't share a row: match's sweep crosses
every column between its turn and the entry, so it would trample mismatch's
`W`/`s` cells.

v2 removes that conflict by making both paths converge on a SINGLE shared
`s`, so there is only one return corridor.  The trick is to arrange for the
`W` on that corridor to leave the right value in A for *both* paths:

  mismatch arrives with A = glyph^symbol, B = symbol  -> W gives A = symbol
  match    arrives with A = packed,       B = packed  -> W gives A = packed

The match path gets A == B == packed for free: after crossing its literal
(A = packed) it just executes `M` (B = A).  So the shared `W` is a no-op for
match and the recovery swap for mismatch, and the shared `s` then sends the
correct value on either path.

The glyph reload lives on row1 (not on the return corridor) so that the
corridor holds nothing but the shared W/s.  That matters for the bootstrap:
the spawned man has A = 0, so if he ever crossed the shared `s` he would emit
a spurious 0 ahead of the real stream.  Putting the reload on row1 lets `@`
sit at row1's west end and walk straight east into the loop, never touching
the corridor.

Layout (offsets from x0+1; digits = len(str(packed_value))):

  row1: @  >  `  g  `  M  r  W  ~  X  `packed`  M  v
        0  1  2  3  4  5  6  7  8  9  10...     .  x_v
  row2:    ^  s  W  .  .  .  .  .  <  ......    <
           1  2  3  4  5  6  7  8  9           x_v

  MATCH   : X sees 0 -> straight east -> `packed` -> M (B = A = packed) ->
            v drops to row2 at x_v -> `<` west -> glides -> W (no-op, since
            A == B == packed) -> s (sends packed) -> `^` -> row1's `>`.
  MISMATCH: X sees >0 -> turns CW (south) -> lands row2 at +9 `<` -> west ->
            W (A = symbol) -> s (sends symbol) -> `^` -> row1's `>`.
  SPAWN   : `@` at +0 -> east -> `>` -> crosses the glyph literal (A = glyph)
            -> M (B = glyph) -> r, entering the loop in the same register
            state every later pass arrives in.

Room is (digits + 16) wide and 4 tall, so unlike v1's 5-tall room it fits a
standard 4-row tail band alongside base_decoder/expander/restorer rooms.

Only phrases of <= 9 symbols are supported: 92**10 overflows signed 64-bit,
and a single shared `s` can only emit one packed value per glyph.
"""
import sys, os, subprocess

sys.path.insert(0, "/Users/pankdm/programming/icfpc-2026/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program

REPO = "/Users/pankdm/programming/icfpc-2026"
BASE = 92
OFFSET = 31
MAX_PHRASE_SYMBOLS = 9  # 92**10 does not fit in signed 64-bit


def packed_symbols(symbols, base=BASE):
    return sum(s * base**i for i, s in enumerate(symbols))


def packed_text(text, offset=OFFSET, base=BASE):
    return packed_symbols([ord(c) - offset for c in text], base)


def phrase_room_width(packed_value: int) -> int:
    """Width of the room phrase_expander() will draw (borders included)."""
    return len(str(packed_value)) + 16


def phrase_expander(p: Program, x0: int, glyph: int, packed_value: int, row: int) -> int:
    """Draw the 4-tall room described above with its top border on `row`-1.
    Returns content max-x (one cell inside the right border), matching the
    convention base_decoder()/expander() use in build_with_year.py."""
    if not 1 <= glyph <= 9:
        raise ValueError("phrase_expander requires a single-digit glyph")
    digits = str(packed_value)
    base = x0 + 1  # offset 0 of the layout diagram above

    row1 = ["@", ">", "`", str(glyph), "`", "M", "r", "W", "~", "X",
            "`", *digits, "`", "M", "v"]
    x_branch = 9                      # the X cell
    x_v = len(row1) - 1               # the v cell

    row2 = [" ", "^", "s", "W"]
    row2 += ["."] * (x_branch - len(row2))
    row2 += ["<"]                      # mismatch landing, offset x_branch
    row2 += ["."] * (x_v - len(row2))
    row2 += ["<"]                      # match landing, offset x_v
    assert len(row2) == len(row1) == x_v + 1

    width = phrase_room_width(packed_value)
    assert x_v + 3 == width, (x_v, width)
    p.room(x0, row - 1, width, 4)
    for dx, g in enumerate(row1):
        p.put(base + dx, row, g)
    for dx, g in enumerate(row2):
        if g != " ":
            p.put(base + dx, row + 1, g)
    return x0 + width - 2


def base_decoder(p: Program, x0: int, row: int) -> int:
    """Byte-for-byte the base_decoder() from build_with_year.py."""
    row1 = [">", "W", "/", "W", "s", "W", "X", "@", "v"]
    row2 = ["^", "`", "2", "9", "`", "M", "<", "r", "<"]
    p.room(x0, row - 1, 11, 4)
    for dx, g in enumerate(row1):
        p.put(x0 + 1 + dx, row, g)
    for dx, g in enumerate(row2):
        p.put(x0 + 1 + dx, row + 1, g)
    return x0 + 9


def build_test_program(glyph: int, packed_value: int):
    p = Program()
    row = 6
    px = phrase_expander(p, 5, glyph, packed_value, row)
    ux = base_decoder(p, px + 4, row)

    minx, miny, maxx, maxy = p.bounds()
    in_x, in_y = minx - 5, miny
    p.input_room(in_x, in_y)
    p.pipe([(in_x + 3, in_y + 1), (minx - 1, miny + 1)])
    p.pipe([(px + 2, row), (px + 3, row)])
    out_x, out_y = maxx + 3, miny
    p.output_room(out_x, out_y)
    p.pipe([(maxx + 1, row), (out_x - 1, out_y + 1)])
    return p


if __name__ == "__main__":
    glyph = 2
    phrase = " and "
    packed = packed_text(phrase)
    print(f"phrase={phrase!r} packed={packed} room={phrase_room_width(packed)}x4")

    p = build_test_program(glyph, packed)
    print(p.render())

    man_path = "/tmp/phrase_v2.man"
    with open(man_path, "w") as f:
        f.write(p.render() + "\n")
    seq = [5, glyph, 20, glyph, glyph, 3]
    with open("/tmp/phrase_v2_in.txt", "w") as f:
        f.write(" ".join(map(str, seq)))

    result = subprocess.run(
        [sys.executable, "-m", "interpreter", "run", man_path,
         "/tmp/phrase_v2_in.txt", "/tmp/phrase_v2_out.txt", "--tick-limit", "20000"],
        cwd=REPO, capture_output=True, text=True,
    )
    print("STDERR:", result.stderr.strip())
    got = [int(x) for x in open("/tmp/phrase_v2_out.txt").read().split()]
    expected = []
    for s in seq:
        if s == glyph:
            expected.extend(ord(c) - OFFSET for c in phrase)
        else:
            expected.append(s)
    print("expected:", expected)
    print("got:     ", got)
    print("MATCH" if got == expected else "MISMATCH")
