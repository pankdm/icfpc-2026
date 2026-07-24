#!/usr/bin/env python3
"""Builder for the `history-lesson` littleman solution (footprint-only scoring).

PROBLEM: no input; output a fixed 2810-byte ASCII text as decimal codes, then stop.
SCORE = max(width,height)^2 (ticks are free), so minimise the max dimension.

ENCODING SCHEME (base-92 packing + comma-space token + FIFO decode loop)
------------------------------------------------------------------------
The 2810 message bytes (all in 32..122, width 91) are first tokenized: the space
after every comma is omitted, leaving shifted comma (13) as an implicit ", "
token. Other bytes are shifted down by OFFSET=31 (byte -> byte-31, range 1..91).
The symbols are then packed
LSB-first into big integers ("chunks") in base 92:

    chunk = s0 + s1*92 + s2*92^2 + ...   (up to 10 bytes/chunk, <= 18 digits)

Shifting to a 92-wide alphabet (instead of packing the raw 32..122 bytes in
base 123) buys more bytes per chunk for the same 64-bit digit budget: a grid
search over (digit-cap, bytes/chunk) found base 92 + 18 digits + 10 bytes/chunk
as the best uniform packing. This layout uses physical slot widths
(16, 17, 18, 18), reducing the feeder width from 89 to 86 while keeping its
height at 80 rows. The comma-space token reduces the stream from 2810 to 2735
symbols; with the mixed-width rows it takes 317 chunks.
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

A TOKEN EXPANDER first forwards every symbol, then XORs it with 13. A zero result
means the symbol was a comma, so it additionally emits shifted space (1).
Every comma in the fixed text is followed by a space, so no escape is required.

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

Usage:  python3 build.py   (writes history-lesson-v2.man next to this file)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

HERE = os.path.dirname(os.path.abspath(__file__))
I64 = 9223372036854775807


# ------------------------------------------------------------------ tokenization + packing
def tokenize(data, offset=31):
    """Omit spaces after commas; shifted comma 13 becomes the implicit token."""
    symbols, i = [], 0
    while i < len(data):
        if data[i:i + 2] == b', ':
            symbols.append(ord(',') - offset)
            i += 2
        else:
            if data[i] == ord(','):
                raise ValueError('comma-space token requires every comma to be followed by space')
            symbols.append(data[i] - offset)
            i += 1
    return symbols


def pack_chunks(symbols, base=92, maxsymbols=10, digit_widths=(16, 17, 18, 18)):
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
def build(data, base=92, maxbytes=10, digit_widths=(16, 17, 18, 18), offset=31):
    """Build feeder -> base decoder -> comma-space expander -> restorer -> O."""
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

    # decoder room, pulled up against the feeder: the feeder->decoder pipe bends
    # (down 1 cell, then east) instead of running straight down, so the decoder
    # only needs to sit 1 row below the feeder instead of 3 (saves 2 rows).
    p.put(3, feeder_bottom + 1, 'v')
    p.put(3, feeder_bottom + 2, '>')
    DX = 4                          # decoder's left wall (the bend pipe's target)
    dy0 = feeder_bottom + 1
    c0, R = DX + 4, feeder_bottom + 2
    p.put(c0 - 3, R, '@'); p.put(c0 - 2, R, 'r'); p.put(c0 - 1, R, '>')
    seq = ['M', '`'] + list(str(base)) + ['`', 'W', '/', 'W', 's', 'W', 'X']
    for j, ch in enumerate(seq):
        p.put(c0 + j, R, ch)
    cE = c0 + len(seq) - 1
    p.put(cE, R + 1, '<'); p.put(c0 - 1, R + 1, '^')      # q>0 loop-back corridor
    p.put(cE + 1, R, 'r'); p.put(cE + 2, R, 'v'); p.put(cE + 2, R + 1, '<')  # q==0 fetch
    dmaxc = cE + 2
    p.room(DX, dy0, dmaxc - DX + 2, 4)

    # Token expander. Every symbol is forwarded first. XOR with 13 is zero only
    # for comma; that path continues east and emits shifted space (1). Every
    # other symbol turns south immediately. Both paths share the lower return.
    ex0 = dmaxc + 4
    ex_main = R
    p.room(ex0, ex_main - 1, 19, 4)
    p.put(ex0 + 1, ex_main, '@')
    p.text(ex0 + 2, ex_main, '`13`M>>rs~X`1`sv')
    p.put(ex0 + 17, ex_main + 1, '<')
    p.put(ex0 + 12, ex_main + 1, '<')
    p.put(ex0 + 8, ex_main + 1, '^')
    emaxc = ex0 + 17

    # Restorer room, same rows as the decoder: receives a shifted symbol, adds
    # `offset` back, and forwards the real byte to O.
    rx0 = emaxc + 4
    p.put(rx0 + 1, R, '@')
    cx = rx0 + 2
    p.put(cx, R, '`'); cx += 1
    for ch in str(offset):
        p.put(cx, R, ch); cx += 1
    p.put(cx, R, '`'); cx += 1
    p.put(cx, R, 'M'); cx += 1
    p.put(cx, R, '>'); cx += 1     # one-time: face east after setup
    rcol_r = cx
    p.put(cx, R, '>'); cx += 1     # loop-entry: the return corridor lands here and
                                    # must re-face east (landing straight on 'r' would
                                    # leave the runner still facing north -> wall)
    p.put(cx, R, 'r'); cx += 1
    p.put(cx, R, '+'); cx += 1
    p.put(cx, R, 's'); cx += 1
    rcol_v = cx
    p.put(cx, R, 'v')
    p.put(rcol_r, R + 1, '^')
    p.put(rcol_v, R + 1, '<')
    rmaxc = cx
    p.room(rx0, R - 1, rmaxc - rx0 + 2, 4)

    ox = rmaxc + 4
    p.output_room(ox, R - 1)
    p.pipe([(dmaxc + 2, R), (ex0 - 1, R)])                     # decoder -> expander
    p.pipe([(emaxc + 2, R), (rx0 - 1, R)])                     # expander -> restorer
    p.pipe([(rmaxc + 2, R), (ox - 1, R)])                      # restorer -> O
    return p, len(chunks), nrows


if __name__ == '__main__':
    data = open(os.path.join(HERE, 'icfp-history.txt'), 'rb').read()
    p, nchunks, nrows = build(data)
    out = os.path.join(HERE, 'history-lesson-v2.man')
    open(out, 'w').write(p.render() + '\n')
    w, h, score = p.footprint()
    print(f'wrote {out}: {w}x{h} score={score}  chunks={nchunks} rows={nrows}')
