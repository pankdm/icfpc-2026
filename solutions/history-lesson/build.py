#!/usr/bin/env python3
"""Builder for the `history-lesson` littleman solution (footprint-only scoring).

PROBLEM: no input; output a fixed 2810-byte ASCII text as decimal codes, then stop.
SCORE = max(width,height)^2 (ticks are free), so minimise the max dimension.

ENCODING SCHEME (base-123 positional packing + FIFO decode loop)
----------------------------------------------------------------
The 2810 message bytes (all in 32..122) are packed, LSB-first, into big integers
("chunks") in base 123 (123 > max byte, so a byte is recovered directly as
value % 123 -- NO lookup table, NO offset needed):

    chunk = b0 + b1*123 + b2*123^2 + ...   (up to 8 bytes/chunk, <= 17 digits)

A FEEDER room holds the chunks as backtick literals and sends each into a pipe.
A tiny DECODER room reads a chunk V and runs a variable-length divmod loop:

    while V != 0:  rem = V % 123;  emit rem;  V = V // 123

emitting the bytes in order.  Termination is automatic because every stored byte
is >= 32 > 0, so the quotient reaches 0 exactly after the last byte of a chunk.
Chunks stream in FIFO order, so byte order is preserved.  Variable-length decode
means chunks can hold any number of bytes (no padding of the message needed).

Decoder instruction path (base B, one loop iteration), A=V on entry:
    M ` B ` W / W s W X
      M      B:=A (=V)
      `B`    A:=B (load base literal)
      W      swap -> A=V, B=base
      /      A:=V/base (quotient q),  B:=V%base (remainder = byte)
      W      A=byte, B=q
      s      send byte to O pipe
      W      A=q, B=byte
      X      turn by sign(A): q>0 -> keep looping; q==0 -> go fetch next chunk (r)

THREE GOTCHAS discovered (verified against the reference oracle):
  1. The literal parser pairs backticks BOTH horizontally AND vertically and rejects
     any NON-digit (e.g. 's', turn glyphs) sitting between a vertical pair. A dense
     east/west boustrophedon feeder mirrors group layout on west rows, which shifts
     backtick columns by one and sandwiches the 's' -> "non-digit in literal" load
     error. FIX: uniform group width g and per-parity horizontal offsets (east +1,
     west +0) so backtick columns coincide on EVERY row; vertical pairs then enclose
     nothing (adjacent rows) and are always clean.
  2. The parser also rejects a literal whose DIGIT-REVERSE overflows i64 (it checks
     both travel directions). Cap chunks to <= 18 digits (we use 17) so value and
     reverse both fit.
  3. The feeder man must finish on `H` (clean halt, reaped), never walk into a wall:
     a wall fault is FATAL and aborts the whole program before the decoder drains
     the pipe -> truncated output. Same reason `H` is fine here even though the
     decoder never halts (it blocks on an empty `r`; output has already settled).

RESULT: 85x96, score 9216, passes 1/1 (public). This does NOT beat the 81x81 board
best -- see the module docstring notes at the bottom for why and what would.

Usage:  python3 build.py   (writes history-lesson.man next to this file)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

HERE = os.path.dirname(os.path.abspath(__file__))
I64 = 9223372036854775807


# ------------------------------------------------------------------ packing
def pack_chunks(data, base=123, maxbytes=8, maxdig=17, store=lambda b: b):
    """Greedy LSB-first positional packing. Each chunk holds up to `maxbytes`
    bytes and at most `maxdig` decimal digits (so value AND its reverse fit i64).
    `store(b)` maps a byte to its stored symbol (identity for base>=123)."""
    chunks, i, N = [], 0, len(data)
    while i < N:
        chosen, nb = None, 1
        for b in range(min(maxbytes, N - i), 0, -1):
            v = sum(store(data[i + j]) * (base ** j) for j in range(b))
            if len(str(v)) <= maxdig:
                chosen, nb = v, b
                break
        chunks.append(chosen)
        i += nb
    return chunks


# ------------------------------------------------------------------ feeder + decoder
def build(data, base=123, maxbytes=8, digit_width=17, groups_per_row=4):
    """Full program: uniform-width snake feeder -> pipe -> divmod decoder -> O.
    Returns (Program, n_chunks, n_rows). Layout is validity-safe by construction
    (see gotcha #1)."""
    chunks = pack_chunks(data, base, maxbytes, digit_width)
    d, k = digit_width, groups_per_row
    g = d + 3                      # group = ` + d digits + ` + s
    p = Program()
    cL = 1
    contentL = 2
    cR = contentL + k * g + 1      # right turn column (room for the east +1 offset)
    nrows = (len(chunks) + k - 1) // k

    for r in range(nrows):
        y = 1 + r
        east = (r % 2 == 0)
        for gi in range(k):
            idx = r * k + gi
            if idx >= len(chunks):
                break
            ds = str(chunks[idx]).zfill(d)
            if east:                                   # east: offset +1, read L->R
                c = contentL + 1 + gi * g
                cells = ['`'] + list(ds) + ['`', 's']
            else:                                      # west: offset 0, read R->L
                c = contentL + (k - 1 - gi) * g        # idx order = rightmost first
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

    # decoder room, one band below the feeder
    dy0 = feeder_bottom + 3
    c0, R = 4, dy0 + 1
    p.put(c0 - 3, R, '@'); p.put(c0 - 2, R, 'r'); p.put(c0 - 1, R, '>')
    seq = ['M', '`'] + list(str(base)) + ['`', 'W', '/', 'W', 's', 'W', 'X']
    for j, ch in enumerate(seq):
        p.put(c0 + j, R, ch)
    cE = c0 + len(seq) - 1
    p.put(cE, R + 1, '<'); p.put(c0 - 1, R + 1, '^')      # q>0 loop-back corridor
    p.put(cE + 1, R, 'r'); p.put(cE + 2, R, 'v'); p.put(cE + 2, R + 1, '<')  # q==0 fetch
    dmaxc = cE + 2
    p.room(0, dy0, dmaxc + 2, 4)

    ox = dmaxc + 4
    p.output_room(ox, dy0)
    p.pipe([(3, feeder_bottom + 1), (3, feeder_bottom + 2)])   # feeder -> decoder
    p.pipe([(dmaxc + 2, R), (ox - 1, R)])                      # decoder -> O
    return p, len(chunks), nrows


if __name__ == '__main__':
    data = open(os.path.join(HERE, 'icfp-history.txt'), 'rb').read()
    p, nchunks, nrows = build(data)
    out = os.path.join(HERE, 'history-lesson.man')
    open(out, 'w').write(p.render() + '\n')
    w, h, score = p.footprint()
    print(f'wrote {out}: {w}x{h} score={score}  chunks={nchunks} rows={nrows}')
