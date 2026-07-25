#!/usr/bin/env python3
"""Build the fixed-16 padding skeleton .man for reverse-a-list (milestone-1).

Topology mirrors the proven snake5 (I -> top serpentine room -> 16 vertical
lanes -> bottom room -> O) but implements the fixed-16 design:

  C = 2097152 = 1<<21   (> max|value| = 1e6, so every biased real is > 0)

  SEQUENCER (reader+sequencer merged, one wide man; single BP counter, the
  16-count is the snake GEOMETRY):
     B = C
     read n -> BP
     snake 16 lane columns RIGHT->LEFT; per column:
        BP>0 : A = read()+C ; send to lane ; BP--     (biased real, > 0)
        else : A = 0        ; send 0 to lane          (padding)
     => lane_j holds S[15-j],  S = [b0..b_{n-1}, 0..0]

  WRITER (compact loop, position-independent R):
     B = C
     barrier: r nearest = lane0 (leftmost = last filled -> all present) -> S[15]
     then R x15 in reading order (lane1..lane15) -> S[14]..S[0]
     per value: X (A>0?) -> real: A=A-C, send to O ; else skip padding
     => prints reals reversed.

Grid: width 20 (16 lanes at grid cols 3..18, a 1-col return rail at col1, a
blank gap at col2 - exactly snake5's margin discipline). The interior op glyphs
encode the PLANNED hot loops; this milestone-1 skeleton is built to LOAD on the
oracle - end-to-end runtime is NOT yet debugged.
"""

W = 18               # total width (cols 0..17); interior cols 1..16
H = 22               # total height (rows 0..21)
LANE0, LANE15 = 1, 16  # lane pipe grid columns (16 lanes: cols 1..16)


def blank_grid():
    return [[" "] * W for _ in range(H)]


def put(g, r, c, s):
    assert c + len(s) <= W - 1, f"row {r}: '{s}' overruns right wall (c={c}, len={len(s)}, W={W})"
    for i, ch in enumerate(s):
        g[r][c + i] = ch


def room(g, top, left, bottom, right):
    """Draw a rectangular room border with + corners, - / | walls."""
    g[top][left] = g[top][right] = g[bottom][left] = g[bottom][right] = "+"
    for c in range(left + 1, right):
        g[top][c] = g[bottom][c] = "-"
    for r in range(top + 1, bottom):
        g[r][left] = g[r][right] = "|"


def build():
    g = blank_grid()

    # ---- I room (top-left) rows 0..2, cols 0..2 ; outgoing pipe down col1
    room(g, 0, 0, 2, 2)
    g[1][1] = "I"
    g[3][1] = "v"          # input pipe (2 cells) col1, rows 3..4
    g[4][1] = "v"          #   -> attaches to sequencer top wall (row5)

    # ---- SEQUENCER room: top wall row5, interior rows 6..9, bottom wall row10
    SEQ_TOP, SEQ_BOT = 5, 10
    room(g, SEQ_TOP, 0, SEQ_BOT, W - 1)
    # setup row (row6): read count, load bias C, start.
    #   > r b   : face E, A=n, BP=n
    #   `2097152` : cross closing backtick -> A = C   (HORIZONTAL literal, clear)
    #   M       : B = C ; @ : start (man faces E)
    put(g, 6, 1, ">rb`2097152`M@")
    # serpentine body over the 16 lane columns (grid cols 1..16), compressed to
    # 3 rows. Per lane column, the planned cell sequence encodes the d-branch
    # (BP>0 real / else pad) + read + bias + send. Rendered as a valid
    # boustrophedon that LOADS; runtime is not yet debugged.
    put(g, 7, 1, "d+d+d+d+d+d+d+d+")   # d: BP>0 turn (real) ; +: A=A+C bias
    put(g, 8, 1, "srsrsrsrsrsrsrsr")   # s: send lane ; r: read next value
    put(g, 9, 1, "^m^m^m^m^m^m^m^m")   # m: BP-- ; ^: serpentine return
    # (row10 is the bottom wall)

    # ---- 16 vertical lanes (2-cell pipes) at grid cols 1..16, rows 11..12
    for c in range(LANE0, LANE15 + 1):
        g[11][c] = "v"
        g[12][c] = "v"

    # ---- WRITER room: top wall row13, interior rows 14..15, bottom wall row16
    WR_TOP, WR_BOT = 13, 16
    room(g, WR_TOP, 0, WR_BOT, W - 1)
    # compact writer loop (does NOT span the 16 lanes: uses R = reading-order).
    #   @ `2097152` M : B = C (debias)
    #   r  : barrier read lane0 (leftmost = last filled)
    #   X  : test A>0 (biased real) -> turn to debias/print ; else skip
    #   - s: A=A-C ; send to O ;  R: receive next lane in reading order (loop)
    put(g, 14, 1, "@`2097152`MrX-sR")   # 16 chars (cols 1..16)
    put(g, 15, 1, "^<<<<<<<<<<<<dav")    # 16 chars (cols 1..16)

    # ---- output pipe (writer bottom wall row16 -> O), 2 cells at col1
    g[17][1] = "v"
    g[18][1] = "v"
    # ---- O room (below, cols 0..2) rows 19..21
    room(g, 19, 0, 21, 2)
    g[20][1] = "O"

    rows = ["".join(r).rstrip() for r in g]
    return rows


if __name__ == "__main__":
    import sys
    rows = build()
    out = "\n".join(rows) + "\n"
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        open(sys.argv[1], "w").write(out)
    for i, l in enumerate(rows):
        print(f"{i:2d}|{l}")
