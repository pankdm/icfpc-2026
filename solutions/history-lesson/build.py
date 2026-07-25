#!/usr/bin/env python3
"""Builder for the `history-lesson` littleman solution (footprint-only scoring).

PROBLEM: no input; output a fixed 2810-byte ASCII text as decimal codes, then stop.
SCORE = max(width,height)^2 (ticks are free), so minimise the max dimension.

ENCODING SCHEME (base-92 packing + punctuation-space tokens + FIFO decode loop)
-------------------------------------------------------------------------------
The 2810 message bytes (all in 32..122, width 91) are first tokenized: the space
after every comma and colon is omitted. Shifted comma (13) and colon (27) are
therefore implicit ", " and ": " tokens. Other bytes are shifted down by
OFFSET=31 (byte -> byte-31, range 1..91). The symbols are then packed
LSB-first into big integers ("chunks") in base 92:

    chunk = s0 + s1*92 + s2*92^2 + ...   (up to 10 bytes/chunk, <= 18 digits)

Shifting to a 92-wide alphabet (instead of packing the raw 32..122 bytes in
base 123) buys more bytes per chunk for the same 64-bit digit budget: a grid
search over (digit-cap, bytes/chunk) found base 92 + 18 digits + 10 bytes/chunk
as the best uniform packing. This experimental v3 layout uses physical slot widths
(16, 16, 18, 18), making the feeder 85 cells wide. The punctuation tokens reduce
the stream from 2810 to 2697 symbols; with the mixed-width rows it takes 314
chunks.
(18 digits is the true safe ceiling: any
18-digit value and its digit-reverse are both guaranteed < i64 max, so no
per-chunk overflow check can push it further; 19 digits is only sometimes
safe and isn't worth the packing complexity to exploit.)

A FEEDER room holds the chunks as backtick literals and sends each into a pipe.
A DECODER room reads a chunk V and runs a variable-length divmod loop:

    while V != 0:  rem = V % 92;  emit (rem);  V = V // 92

emitting symbols in order. Termination is safe because no chunk ends in symbol
0, so the quotient reaches 0 exactly after the last symbol. Chunks stream in
FIFO order, so symbol order is preserved.

Two streaming TOKEN EXPANDER rooms sit in series. The first forwards every
symbol and expands comma (13) to comma-space; the second does the same for
colon (27). FIFO pipes preserve the order of emitted punctuation and spaces.
Every comma and colon in the fixed text is followed by a space, so no escape is
required.

A small RESTORER room sits between the decoder and O: it adds OFFSET back
(`+`) to each value the decoder emits, then forwards the true byte to O. This
is a separate one-time-cost room (doesn't scale with data size) rather than
folding the +OFFSET into the decoder's own divmod loop, because the divmod
loop already uses both registers (A=quotient/remainder scratch, B=base) --
stealing a register there to also hold OFFSET would mean re-deriving the
loop's register choreography. The restorer's loop body is a clean two-row
racetrack:

    row1: @ ` 3 1 ` M > r + s v
    row2:             ^     <

  @`31`M>   one-time setup: B := OFFSET (31), face east.
  r         receive a shifted byte from the decoder.
  +         A := A + B  =>  restores the true ASCII byte.
  s         send it to O.
  v / ^ / < turn south, loop back west along row2, turn north back onto 'r'.

THREE GOTCHAS discovered (verified against the reference oracle):
  1. The literal parser pairs backticks BOTH horizontally AND vertically and rejects
     any NON-digit (e.g. 's', turn glyphs) sitting between a vertical pair. A dense
     east/west boustrophedon feeder mirrors group layout on west rows, which shifts
     backtick columns by one and sandwiches the 's' -> "non-digit in literal" load
     error. FIX: uniform group width g and per-parity horizontal offsets (east +1,
     west +0) so backtick columns coincide on EVERY row; vertical pairs then enclose
     nothing (adjacent rows) and are always clean.
  2. The parser also rejects a literal whose DIGIT-REVERSE overflows i64 (it checks
     both travel directions). Cap chunks so the value AND its reverse fit -- see the
     18-digit note above (both directions are always safe at <=18 digits).
  3. The feeder man must finish on `H` (clean halt, reaped), never walk into a wall:
     a wall fault is FATAL and aborts the whole program before the decoder/restorer
     drain the pipes -> truncated output. Same reasoning applies to the decoder and
     restorer, which is why neither ever halts either -- they just block forever on
     an empty `r` once the feeder is done, which is free (output has already settled).

Usage:  python3 build.py   (writes history-lesson-v4.man next to this file)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

HERE = os.path.dirname(os.path.abspath(__file__))
I64 = 9223372036854775807


# ------------------------------------------------------------------ tokenization + packing
PUNCT_SPACE_TOKENS = (b',', b':', b';', b'.')


def tokenize(data, offset=31):
    """Omit spaces after comma/colon/semicolon/period; their shifted values become tokens."""
    symbols, i = [], 0
    while i < len(data):
        ch = data[i:i + 1]
        if ch in PUNCT_SPACE_TOKENS and data[i:i + 2] == ch + b' ':
            symbols.append(data[i] - offset)
            i += 2
        else:
            if ch in PUNCT_SPACE_TOKENS:
                raise ValueError(f'punctuation-space token {ch!r} requires a following space')
            symbols.append(data[i] - offset)
            i += 1
    return symbols


def pack_chunks(symbols, base=92, maxsymbols=10, digit_widths=(16, 16, 18, 18)):
    """Pack symbols into alternating rows with fixed physical literal widths.

    Logical chunk order runs left-to-right on eastbound rows and right-to-left
    on westbound rows, so the per-chunk digit cap is reversed on odd rows.
    """
    chunks, i, N = [], 0, len(symbols)
    k = len(digit_widths)
    while i < N:
        row, slot = divmod(len(chunks), k)
        physical_slot = slot if row % 2 == 0 else k - 1 - slot
        maxdig = digit_widths[physical_slot]
        chosen, ns = None, 1
        for n in range(min(maxsymbols, N - i), 0, -1):
            v = sum(symbols[i + j] * (base ** j) for j in range(n))
            if len(str(v)) <= maxdig:
                chosen, ns = v, n
                break
        if chosen is None:
            raise ValueError(f'cannot terminate a chunk at symbol offset {i}')
        chunks.append(chosen)
        i += ns
    return chunks


# ------------------------------------------------ feeder + decoder + expander + restorer
def build(data, base=92, maxbytes=10, digit_widths=(16, 16, 18, 18), offset=31):
    """Build feeder -> base decoder -> punctuation expander -> restorer -> O."""
    symbols = tokenize(data, offset)
    chunks = pack_chunks(symbols, base, maxbytes, digit_widths)
    k = len(digit_widths)
    group_widths = [d + 3 for d in digit_widths]  # ` + digits + ` + s
    group_starts = [sum(group_widths[:i]) for i in range(k)]
    p = Program()
    cL = 1
    contentL = 2
    cR = contentL + sum(group_widths) + 1
    nrows = (len(chunks) + k - 1) // k

    for r in range(nrows):
        y = 1 + r
        east = (r % 2 == 0)
        for gi in range(k):
            idx = r * k + gi
            if idx >= len(chunks):
                break
            physical_slot = gi if east else k - 1 - gi
            d = digit_widths[physical_slot]
            ds = str(chunks[idx]).zfill(d)
            if east:                                   # east: offset +1, read L->R
                c = contentL + 1 + group_starts[physical_slot]
                cells = ['`'] + list(ds) + ['`', 's']
            else:                                      # west: offset 0, read R->L
                c = contentL + group_starts[physical_slot]
                cells = ['s', '`'] + list(ds[::-1]) + ['`']
            for j, ch in enumerate(cells):
                p.put(c + j, y, ch)
        # turn glyphs (entry '>'/'<', exit 'v'; last row exits with 'H')
        if east:
            if r > 0:
                p.put(cL, y, '>')
            p.put(cR, y, 'H' if r == nrows - 1 else 'v')
        else:
            p.put(cR, y, '<')
            p.put(cL, y, 'H' if r == nrows - 1 else 'v')
    p.put(cL, 1, '@')              # man starts top-left, facing east

    feeder_bottom = nrows + 1
    p.room(0, 0, cR + 2, nrows + 2)

    # Every tail block (decoder + expanders + restorer) places its own literal's
    # backticks at relative offset +2/+5 from its own left wall. The feeder's
    # boustrophedon alignment trick (gotcha #1) means the SAME backtick columns
    # repeat on every feeder row, so any tail block landing on one of those
    # columns vertical-pairs with a feeder literal across the wall in between
    # ("non-digit in literal"). Find the actual forbidden columns from the
    # rendered feeder (rows 1 and 2, covering both east/west parity) and use a
    # greedy leftmost search for every block's position instead of guessing.
    forbidden_cols = {x for y in (1, 2) for x in range(cR + 2) if p.get(x, y) == '`'}

    def leftmost_safe_x(prev_max, gap_min=4, offsets=(2, 5)):
        x = prev_max + gap_min
        while any((x + o) in forbidden_cols for o in offsets):
            x += 1
        return x

    # decoder room, pulled up against the feeder: the feeder->decoder pipe bends
    # (down 1 cell, then east) instead of running straight down, so the decoder
    # only needs to sit 1 row below the feeder instead of 3 (saves 2 rows).
    DX = leftmost_safe_x(-3)         # decoder's left wall; -3 so DX starts >= 1
                                      # (room for the bend-pipe cell at DX-1)
    p.put(DX - 1, feeder_bottom + 1, 'v')
    p.put(DX - 1, feeder_bottom + 2, '>')
    dy0 = feeder_bottom + 1
    R = feeder_bottom + 2
    assert base == 92, "decoder block below hardcodes the `29` (->92 westward) base literal"
    # One shared 9x2 block does spawn + first-fetch + the full divmod loop (both
    # "more digits in this chunk" and "fetch the next chunk" re-enter the same
    # path). '`29`' read westward crosses '9' then '2' -> value 92.
    #   row R:    >  W  /  W  s  W  X  @  v
    #   row R+1:  ^  `  2  9  `  M  <  r  <
    row1 = ['>', 'W', '/', 'W', 's', 'W', 'X', '@', 'v']
    row2 = ['^', '`', '2', '9', '`', 'M', '<', 'r', '<']
    for j, ch in enumerate(row1):
        p.put(DX + 1 + j, R, ch)
    for j, ch in enumerate(row2):
        p.put(DX + 1 + j, R + 1, ch)
    dmaxc = DX + 1 + len(row1) - 1   # rightmost content column ('v'/'<')
    p.room(DX, dy0, dmaxc - DX + 2, 4)

    # A streaming one-token expander: forward every input symbol, then test it
    # with XOR. A matching token yields zero and takes the east path, which emits
    # each value in `emit` (shifted space (1) by default; a bigram token emits
    # its two decoded symbols instead); every other value takes the lower return
    # path. Same shared-loop trick as the decoder/restorer: '>' is the loop-entry,
    # '@' is a harmless pass-through visited only by the match branch, and the
    # token literal on row2 is stored digit-reversed for westward reading.
    #   row R:    >  M  r  s  ~  X  <emit values, each `v`+digits+`s`>  v
    #   row R+1:  ^  `  d  d  `  <  ...blank...                     @  <
    def expander(ex0, token, emit=(1,), row=None):
        row = R if row is None else row
        emit_cells = []
        for v in emit:
            emit_cells += [str(v)] if 0 <= v <= 9 else ['`'] + list(str(v)) + ['`']
            emit_cells.append('s')
        row1 = ['>', 'M', 'r', 's', '~', 'X'] + emit_cells + ['v']
        n = len(row1)
        row2 = [' '] * n
        row2[0] = '^'
        row2[1:5] = ['`'] + list(str(token)[::-1]) + ['`']
        row2[5] = '<'            # mismatch entry, matches row1's 'X'
        row2[n - 2] = '@'        # pass-through, only visited by the match branch
        row2[n - 1] = '<'        # match entry, matches row1's 'v'
        p.room(ex0, row - 1, n + 2, 4)
        for j, ch in enumerate(row1):
            p.put(ex0 + 1 + j, row, ch)
        for j, ch in enumerate(row2):
            p.put(ex0 + 1 + j, row + 1, ch)
        return ex0 + 1 + n - 1

    comma_x = leftmost_safe_x(dmaxc)
    comma_max = expander(comma_x, 13)
    colon_x = leftmost_safe_x(comma_max)
    colon_max = expander(colon_x, 27)
    semicolon_x = leftmost_safe_x(colon_max)
    semicolon_max = expander(semicolon_x, ord(';') - offset)
    period_x = leftmost_safe_x(semicolon_max)
    period_max = expander(period_x, ord('.') - offset)

    # Restorer room, same rows as the decoder: one shared 7x2 block does spawn +
    # first-receive + the full receive/restore/send loop, same trick as the
    # decoder ('@' sits mid-loop as a harmless pass-through on every re-entry).
    # '`13`' read westward crosses '3' then '1' -> value 31 (the OFFSET).
    #   row R:    >     M  r  +  s  v
    #   row R+1:  ^  `  1  3  `  @  <
    assert offset == 31, "restorer block below hardcodes the `13` (->31 westward) offset literal"
    rx0 = leftmost_safe_x(period_max)
    row1 = ['>', ' ', 'M', 'r', '+', 's', 'v']
    row2 = ['^', '`', '1', '3', '`', '@', '<']
    for j, ch in enumerate(row1):
        p.put(rx0 + 1 + j, R, ch)
    for j, ch in enumerate(row2):
        p.put(rx0 + 1 + j, R + 1, ch)
    rmaxc = rx0 + len(row1)
    p.room(rx0, R - 1, rmaxc - rx0 + 2, 4)

    ox = rmaxc + 4
    p.output_room(ox, R - 1)
    p.pipe([(dmaxc + 2, R), (comma_x - 1, R)])                 # decoder -> comma
    p.pipe([(comma_max + 2, R), (colon_x - 1, R)])             # comma -> colon
    p.pipe([(colon_max + 2, R), (semicolon_x - 1, R)])         # colon -> semicolon
    p.pipe([(semicolon_max + 2, R), (period_x - 1, R)])        # semicolon -> period
    p.pipe([(period_max + 2, R), (rx0 - 1, R)])                # period -> restorer
    p.pipe([(rmaxc + 2, R), (ox - 1, R)])                      # restorer -> O
    return p, len(chunks), nrows


if __name__ == '__main__':
    data = open(os.path.join(HERE, 'icfp-history.txt'), 'rb').read()
    p, nchunks, nrows = build(data)
    out = os.path.join(HERE, 'history-lesson-v4.man')
    open(out, 'w').write(p.render() + '\n')
    w, h, score = p.footprint()
    print(f'wrote {out}: {w}x{h} score={score}  chunks={nchunks} rows={nrows}')
