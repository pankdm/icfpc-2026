#!/usr/bin/env python3
"""Complete history-lesson program using the route-B dispatcher.

Deliberately NOT compacted: rooms are spread out and P1 is a naive preload row
rather than build_ring's tightly-packed table.  The point is a *working,
oracle-verified* end-to-end artifact that someone can compact afterwards.  The
champion (81x81, score 6561) is untouched and lives in
solutions/history-lesson/best/81x81.man.

What is different from the champion
-----------------------------------
Symbols 60..65 name bytes that never occur in the text, so they are dead
weight.  Here they become one-symbol dictionary references to ring positions
17..22, instead of costing an `ESC, position` pair.  That takes the dictionary
from 9 direct entries to 15 and the stream from 2042 symbols to ~1951.

Everything else -- the base-92 packing, the feeder DP, DECODER, YEAR, UNPACK --
is build_ring's, unchanged.

    python3 build_full_routeB.py          # writes full_routeB.man
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "solutions", "history-lesson"))

from littleman import Program                       # noqa: E402
import build_ring as base                           # noqa: E402
from build_rig import disp_rows                     # noqa: E402

RUN = (60, 65)          # recycled symbols -> ring positions 17..22
FEEDER_W = 81


def encode():
    """Return (symbols, ordered ring values, position of each).

    Ring positions are the *preload order*, which this builder controls
    completely because P1 is a plain preload row.  That is the whole reason
    this artifact is easy to get right and build_ring's version is not: there,
    the position of an entry is decided by a width-sorted grid layout.
    """
    recycled = list(range(RUN[0], RUN[1] + 1))
    low_free = list(base.SMALL_FREE)
    base.SMALL_FREE = low_free + recycled
    stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
    base.SMALL_FREE = low_free

    singles = [i for i, (p, s) in enumerate(phrases) if s is True]
    pairs = [i for i, (p, s) in enumerate(phrases) if s is False]
    assert len(singles) <= len(low_free) + len(recycled)

    val = lambda i: base.pack128(base.phrase_bytes(phrases[i][0]))
    ring = {}                       # position -> packed value
    sym_of = {}                     # phrase index -> stream symbol(s)

    # positions 1..16: the low free slots carry phrases, the rest spell bytes
    low_singles = singles[:len(low_free)]
    for i, pos in zip(low_singles, low_free):
        ring[pos] = val(i)
        sym_of[i] = [pos]
    for v in range(1, 17):
        ring.setdefault(v, base.pack128(base.spell(v)))

    # positions 17..22: the recycled run, reached by symbol position + 43
    hi_singles = singles[len(low_free):]
    for n, i in enumerate(hi_singles):
        pos = 17 + n
        ring[pos] = val(i)
        sym_of[i] = [pos + 43]
    nxt = 17 + len(hi_singles)

    # the rest are ordinary escape pairs
    for i in pairs:
        ring[nxt] = val(i)
        sym_of[i] = [base.ESC, nxt]
        nxt += 1

    symbols = []
    for t in stream:
        symbols.extend([t] if t >= 0 else sym_of[-t - 1])
    assert all(0 <= s < base.B1 for s in symbols), "symbol out of range"

    # semantic check against the text, mirroring DISP + YEAR + UNPACK
    mid, i = [], 0
    while i < len(symbols):
        v = symbols[i]; i += 1
        if v == 0:
            mid.append(0)
        elif v <= 16:
            mid.append(ring[v])
        elif v == base.ESC:
            mid.append(ring[symbols[i]]); i += 1
        elif RUN[0] <= v <= RUN[1]:
            mid.append(ring[v - 43])
        else:
            mid.append(v + 31)
    out, code, bp = bytearray(), base.pack128(
        f"; {base.FIRST_YEAR}: ".encode()), 10
    for v in mid:
        if v == 0:
            v, code, bp = code, code + base.STEP, bp - 1
            if bp == 0:
                code += base.CORR; bp = 10
        while v:
            v, r = divmod(v, base.B2)
            out.append(r)
    assert bytes(out) == base.TEXT, "encoding does not reproduce the text"
    order = [ring[p] for p in sorted(ring)]
    return symbols, order


def build():
    symbols, ring_order = encode()
    bands = base.optimize_feeder(symbols, FEEDER_W)

    p = Program()
    frows = base.variable_feeder(p, bands, FEEDER_W)
    G = frows + 2                     # two free gap rows under the feeder
    Y = G + 2                         # rooms start here

    # --- rooms, spread out, each with its own pipe corridor ----------------
    base.paste_room(p, 0, Y, base.DECODER_ROWS)          # x0..x10,  4 rows
    p.room(20, Y, 40, 8)                                 # DISP x20..x59
    for dy, row in enumerate(disp_rows()):
        for dx, ch in enumerate(row):
            if ch != " ":
                p.put(21 + dx, Y + 1 + dy, ch)
    yw, yh = base.paste_room(p, 70, Y, base.year_rows())  # x70..x98, 7 rows
    assert (yw, yh) == (29, 7)
    base.paste_room(p, 110, Y, base.UNPACK_ROWS)          # x110..x121, 4 rows
    p.output_room(130, Y)                                 # x130..x132

    # --- P1: a plain preload row, then the six-cell r/s pump ---------------
    py = Y + 14
    cells = ["@"]
    for v in ring_order + [0]:                            # 0 is the sentinel
        cells += ["`", *str(v), "`", "s"]
    e = 1 + len(cells)
    p.room(0, py, e + 4, 5)
    for i, ch in enumerate(cells):
        p.put(1 + i, py + 3, ch)
    p.put(e, py + 3, "^"); p.put(e, py + 2, "r")
    p.put(e, py + 1, ">"); p.put(e + 1, py + 1, "v")
    p.put(e + 1, py + 2, "s"); p.put(e + 1, py + 3, "<")

    # --- pipes -------------------------------------------------------------
    p.pipe([(1, G), (1, G + 1)], end_direction="S")            # feeder->DECODER
    p.pipe([(11, Y + 2), (19, Y + 2)], end_direction="E")      # DECODER->DISP
    # A pipe's source cell must step *away* from the wall it attaches to, so
    # this rises one row before turning east.
    p.pipe([(25, Y - 1), (25, Y - 2), (84, Y - 2), (84, Y - 1)],
           end_direction="S")                                   # DISP->YEAR
    p.pipe([(99, Y + 4), (105, Y + 4), (105, Y + 2),
            (109, Y + 2)], end_direction="E")                  # YEAR->UNPACK
    p.pipe([(122, Y + 2), (126, Y + 2), (126, Y + 1),
            (129, Y + 1)], end_direction="E")                  # UNPACK->O
    # ring: DISP east wall row5 -> P1 north wall, and back to east wall row4
    # The two legs never share a row or a column: the outbound one drops at
    # x=64 and runs west along P1's north face, the return climbs at x=70.
    p.pipe([(60, Y + 7), (64, Y + 7), (64, py - 1), (30, py - 1)],
           end_direction="S")
    p.pipe([(66, py - 1), (66, Y + 6), (60, Y + 6)], end_direction="W")
    return p


if __name__ == "__main__":
    prog = build()
    out = os.path.join(HERE, "full_routeB.man")
    prog.save(out)
    w, h, score = prog.footprint()
    print(f"wrote {out}: {w}x{h} (score would be {score}; not compacted)")
