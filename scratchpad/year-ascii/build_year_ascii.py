"""Prototype: integer year -> ASCII digits, written straight into the output pipe.

Question this answers: history-lesson currently keeps its year prefix as a
*base-128 packed ASCII* value and advances it with a magic STEP literal plus a
decade CORRection (see build_ring.py:year_rows).  That trick cannot cross the
1999 -> 2000 century carry, which is why FIRST_YEAR is 2000 and 1996..1999 are
spelled out in the symbol stream.  Here we instead keep the year as a plain
integer and convert it to ASCII at emit time.  An integer counter advances with
a bare `+1`, and the century carry is free.

Protocol of the prototype (a small stand-in for the real symbol stream):

    input:  a sequence of integers.  0 is an ESCAPE marker meaning "the next
            value is a year"; every other value is a raw ASCII byte.
    output: raw bytes pass through untouched; an escaped year Y is emitted as
            the full 8-byte prefix  "; YYYY: ".

    e.g.  0 1999 88 0 2000   ->   "; 1999: X; 2000: "

Conversion gadget (MSB-first, no packing, no scratch storage):

    Z = Y + 48000
    repeat 4 times:
        q, rem = divmod(Z, 1000)    # q is already the ASCII digit: 48 + digit
        send q
        Z = rem * 10 + 48000

    Biasing by 48*1000 makes the quotient come out pre-shifted into ASCII, so no
    separate "+48" stage is needed; rescaling the remainder by 10 keeps the
    divisor a single constant, so the whole loop is one 17-cell run.  Digits
    come out most-significant first, i.e. already in output order.

Registers: A holds Z, B is scratch for the divisor/multiplier, BP is the
iteration counter.  Nothing else is live, which is what makes this fit in one
room (there is no third register and self-loop pipes are a load error).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from layout import Layout  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def lit(value, west=False):
    """Cells for a backtick literal, in *grid* (left-to-right) order.

    Literals are read in the walk direction, so a westbound literal must be
    written with its digits reversed in the grid.
    """
    digits = str(value)
    if west:
        digits = digits[::-1]
    return "`" + digits + "`"


# ── the compute room, as interior rows (ix, iy) ────────────────────────────
# iy=0  JOIN     (westward)  B:=A; A:=48000; A+=B; BP--; branch; tail ": "
# iy=1  transit  (westward)  loop back-edge from JOIN down to the LOOP row
# iy=2  LOOP     (eastward)  one ASCII digit per pass
# iy=3  HEAD     (eastward)  read symbol, dispatch, "; " + BP:=5 + read year
# iy=4  raw send
# iy=5  spawn / raw return
#
# column 0  = left bus (JOIN tail -> HEAD)
# column 22 = right bus (YEAR path and LOOP end -> JOIN)

def compute_rows():
    W = 23
    grid = [[" "] * W for _ in range(6)]

    def put(iy, ix, s):
        for k, ch in enumerate(s):
            assert grid[iy][ix + k] == " ", (iy, ix + k, grid[iy][ix + k])
            grid[iy][ix + k] = ch

    # --- iy=0: JOIN, walked westward from ix=22 down to ix=0 ---------------
    put(0, 22, "<")                       # entry merge (arrives heading north)
    put(0, 21, "M")                       # B = A            (A = Y or 10*rem)
    put(0, 14, lit(48000, west=True))     # A = 48000        (ix 20..14)
    put(0, 13, "+")                       # A = 48000 + B    (= Z)
    put(0, 12, "m")                       # BP--
    put(0, 11, "a")                       # BP>0 -> ccw (south, into LOOP)
    put(0, 7, lit(58, west=True))         # ...else fall through: A = ':'
    put(0, 6, "s")
    put(0, 2, lit(32, west=True))         # A = ' '
    put(0, 1, "s")
    put(0, 0, "v")                        # -> left bus, back to HEAD

    # --- iy=1: back-edge transit ------------------------------------------
    put(1, 11, "<")
    put(1, 1, "v")
    put(1, 22, "^")                       # right bus (LOOP end -> JOIN)

    # --- iy=2: the digit LOOP, walked eastward ----------------------------
    put(2, 1, ">")
    put(2, 2, "M")                        # B = Z
    put(2, 3, lit(1000))                  # A = 1000         (ix 3..8)
    put(2, 9, "W")                        # A = Z, B = 1000
    put(2, 10, "/")                       # A = 48+digit, B = Z % 1000
    put(2, 11, "s")                       # emit the ASCII digit
    put(2, 12, "W")                       # A = rem
    put(2, 13, "M")                       # B = rem
    put(2, 14, lit(10))                   # A = 10           (ix 14..17)
    put(2, 18, "*")                       # A = 10 * rem
    put(2, 22, "^")                       # -> right bus -> JOIN

    # --- iy=3: HEAD + escape handling -------------------------------------
    put(3, 0, ">")                        # entry merge (left bus / raw return)
    put(3, 1, "r")                        # A = next symbol
    put(3, 2, "X")                        # A>0 -> cw (south, raw byte)
    put(3, 3, lit(59))                    # A = ';'          (ix 3..6)
    put(3, 7, "s")
    put(3, 8, lit(32))                    # A = ' '          (ix 8..11)
    put(3, 12, "s")
    put(3, 13, "5")
    put(3, 14, "b")                       # BP = 5  (1 init pass + 4 digits)
    put(3, 15, "r")                       # A = the year
    put(3, 22, "^")                       # -> right bus -> JOIN

    # --- iy=4/5: raw byte passthrough and the spawn -----------------------
    put(4, 2, "s")                        # send the raw byte unchanged
    put(4, 0, "^")
    put(5, 0, "^")
    put(5, 1, "@")                        # spawn: east, bounce west, up the bus
    put(5, 2, "<")

    return ["".join(row) for row in grid]


# ── the year source, for the counter variant ───────────────────────────────
# A free-running counter that pushes 1997, 1998, 1999, ... into a pipe and
# parks (blocked, for free) whenever the pipe is full.  Nothing ever receives
# here, so A holds the year permanently and the whole loop is `s M 1 +`.
# Row 1 is walked westward from ix=7, so it reads `s M 1 +` right-to-left.
CTR_ROWS = [
    "@`1997`v",
    "  v+1Ms<",
    "  >    ^",
]


def build(counter=False, first_year=1997):
    lay = Layout()
    p = lay.p
    rows = compute_rows()
    w, h = len(rows[0]) + 2, len(rows) + 2

    lay.input_room(0, 0)                       # y 0..2
    lay.room(0, 5, w, h)                       # y 5..5+h-1, interior at (1,6)
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch != " ":
                lay.put(1 + dx, 6 + dy, ch)
    out_y = 5 + h + 2
    lay.output_room(0, out_y)

    lay.pipe([(1, 3), (1, 4)])                 # I -> compute
    lay.pipe([(1, 5 + h), (1, 5 + h + 1)])     # compute -> O

    if counter:
        # CTR sits east of the compute room; its pipe attaches to the east
        # wall so that the *nearest incoming pipe* for the year `r` (deep in
        # the room, ix=15) is CTR, while the stream `r` (ix=1) stays locked
        # onto the input pipe hanging off the north-west corner.
        cx = w + 2                             # 2 free cells for the pipe
        crows = [r.replace("1997", str(first_year)) for r in CTR_ROWS]
        lay.room(cx, 5, len(crows[0]) + 2, len(crows) + 2)
        for dy, row in enumerate(crows):
            for dx, ch in enumerate(row):
                if ch != " ":
                    lay.put(cx + 1 + dx, 6 + dy, ch)
        lay.pipe([(cx - 1, 7), (cx - 2, 7)])   # CTR -> compute, westward
    return p


if __name__ == "__main__":
    for counter in (False, True):
        prog = build(counter=counter)
        name = "year-ascii-counter.man" if counter else "year-ascii.man"
        prog.save(os.path.join(HERE, name))
        print(f"=== {name} ===")
        print(prog.render())
        print("footprint:", prog.footprint())
