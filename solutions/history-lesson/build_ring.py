#!/usr/bin/env python3
"""history-lesson: ring-dictionary build.

Pipeline: feeder ->(chunks) decoder(/92) ->(syms) DISP (classify + ring
lookup) ->(raw ascii / packed / 0) year ->(values) unpack(/128) -> O.

Stream alphabet (base 92): 0 year marker, 1..16 ring lookups (identities and
phrase glyphs; 13 = ", "), 17 stolen (forced phrase), 18..91 ordinary
(passthrough +31 done in DISP), ESC=29 pair refs [29, k] with k = ring
position 17..N.  Ring entries are packed base-128 raw ASCII, LSB first.
The ring is a pipe loop DISP <-> P1 (preloaded by P1, kept canonical via
sentinel -1 and full-rotation restore).

Rooms were unit-verified in scratchpad/history-ring/ (roomsim + tests).

Usage:
  python3 build_ring.py                         # reproduce best/81x81.man
  python3 build_ring.py --legacy 82             # reproduce best/82x82.man
  python3 build_ring.py --narrow                # build candidates/81x82.man
  python3 build_ring.py --legacy                # reproduce history-ring.man
  python3 build_ring.py --legacy 82 --variable  # reproduce 82x83 intermediate
"""
from __future__ import annotations

import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
from littleman import Program
from optimize_feeder import Band, optimize_feeder

B1 = 92
B2 = 128
ESC = 29
STOLEN = (8, 17)
SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16]
FIRST_YEAR, LAST_YEAR = 2000, 2026
TEXT = open(os.path.join(HERE, "icfp-history.txt"), "rb").read()

STEP = B2 ** 5
CORR = B2 ** 4 - 10 * B2 ** 5
NARROW_EXTRA_PAIRS = 3


# ---------------------------------------------------------------- encoder --

def tokenize(data: bytes) -> list[int]:
    # Keep the predictable year prefixes out of the general dictionary.  A
    # single zero later asks the stateful YEAR room to emit the next prefix.
    # Token 13 is likewise reserved for the frequent two-byte ", " spelling.
    toks, i, year = [], 0, FIRST_YEAR
    while i < len(data):
        if year <= LAST_YEAR:
            b = f"; {year}: ".encode()
            if data.startswith(b, i):
                toks.append(0); i += len(b); year += 1; continue
        if data[i:i + 2] == b", ":
            toks.append(13); i += 2; continue
        toks.append(data[i] - 31); i += 1
    assert year == LAST_YEAR + 1
    return toks


def spell(tok: int) -> bytes:
    return b", " if tok == 13 else bytes([tok + 31])


def phrase_bytes(pat) -> bytes:
    return b"".join(spell(t) for t in pat)


def pack128(bs: bytes) -> int:
    v = 0
    for i, c in enumerate(bs):
        v += c * (B2 ** i)
    assert 0 < v < 2 ** 63
    return v


def fits_literal(v: int) -> bool:
    """Literals must fit i64 when read in either direction."""
    s = str(v)
    return v < 2 ** 63 and int(s[::-1]) < 2 ** 63


def count_nonoverlap(stream, pat):
    n, m, i, t = len(stream), len(pat), 0, 0
    while i <= n - m:
        if tuple(stream[i:i + m]) == pat:
            t += 1; i += m
        else:
            i += 1
    return t


def replace_nonoverlap(stream, pat, rep):
    out, i, n, m = [], 0, len(stream), len(pat)
    while i < n:
        if tuple(stream[i:i + m]) == pat:
            out.extend(rep); i += m
        else:
            out.append(stream[i]); i += 1
    return out


def choose_phrases(stream):
    # The dictionary is deliberately selected against *source-grid* cost, not
    # merely compressed-stream length: every chosen phrase also consumes a
    # literal and a send instruction in P1.
    dig1 = math.log10(B1)
    forbidden = set(STOLEN) | {0, ESC}
    singles_left = len(SMALL_FREE)
    pairs_left = 91 - 17 + 1
    phrases = []
    for v in STOLEN:
        stream = replace_nonoverlap(stream, (v,), [-len(phrases) - 1])
        phrases.append(((v,), False))
        pairs_left -= 1
    while True:
        n = len(stream)
        cand = set()
        for m in range(2, 10):
            local = Counter()
            for i in range(n - m + 1):
                seg = tuple(stream[i:i + m])
                if any((s in forbidden) or s < 1 for s in seg):
                    continue
                if len(phrase_bytes(seg)) > 9:
                    continue
                packed = pack128(phrase_bytes(seg))
                if not fits_literal(packed) or len(str(packed)) > 18:
                    continue
                local[seg] += 1
            cand.update(seg for seg, c in local.items() if c >= 2)
        best = (1e-9, None, None)
        for seg in cand:
            m = len(seg)
            t = count_nonoverlap(stream, seg)
            if t < 2:
                continue
            table_cost = len(str(pack128(phrase_bytes(seg)))) + 3
            if singles_left:
                gain = dig1 * (m - 1) * t - table_cost
                if gain > best[0]:
                    best = (gain, seg, True)
            if pairs_left:
                gain = dig1 * (m - 2) * t - table_cost
                if gain > best[0]:
                    best = (gain, seg, False)
        if best[1] is None:
            break
        _, seg, single = best
        if single:
            singles_left -= 1
        else:
            pairs_left -= 1
        stream = replace_nonoverlap(stream, seg, [-len(phrases) - 1])
        phrases.append((seg, single))
    return stream, phrases


def add_best_pair_phrases(stream, phrases, count):
    """Add escape-pair phrases ranked only by symbol-stream reduction.

    The main dictionary optimizer charges P1 source cells.  The narrow build
    has already made room for ``count`` more constants, so their relevant
    objective is `(tokens - 2) * occurrences`.  Recompute after every choice
    because candidates overlap.
    """
    forbidden = set(STOLEN) | {0, ESC}
    chosen = []
    for _ in range(count):
        candidates = []
        n = len(stream)
        for m in range(3, 10):
            local = Counter()
            for i in range(n - m + 1):
                seg = tuple(stream[i:i + m])
                if any((s in forbidden) or s < 1 for s in seg):
                    continue
                if len(phrase_bytes(seg)) > 9:
                    continue
                packed = pack128(phrase_bytes(seg))
                if not fits_literal(packed) or len(str(packed)) > 18:
                    continue
                local[seg] += 1
            for seg, occurrences in local.items():
                if occurrences < 2:
                    continue
                hits = count_nonoverlap(stream, seg)
                saving = (m - 2) * hits
                if saving > 0:
                    # Prefer a shorter preload literal after symbol saving.
                    digits = len(str(pack128(phrase_bytes(seg))))
                    candidates.append(
                        (saving, -digits, m, hits, phrase_bytes(seg), seg)
                    )
        if not candidates:
            raise ValueError(f"only found {len(chosen)} extra pair phrases")
        _, _, _, _, _, seg = max(candidates)
        stream = replace_nonoverlap(stream, seg, [-len(phrases) - 1])
        phrases.append((seg, False))
        chosen.append(phrase_bytes(seg))
    return stream, chosen


def build_encoding(table_budget=None, extra_pair_count=0, tail_constants=False,
                   west_first=False):
    stream, phrases = choose_phrases(tokenize(TEXT))
    if extra_pair_count:
        stream, chosen = add_best_pair_phrases(
            stream, phrases, extra_pair_count
        )
        if extra_pair_count == NARROW_EXTRA_PAIRS:
            assert set(chosen) == {b"Baltim", b", Italy", b"iotis, "}

    def table_cells(phr):
        # entries + identities + placeholders + sentinel, in preload cells
        singles = [i for i, (p, s) in enumerate(phr) if s is True]
        pairs = [i for i, (p, s) in enumerate(phr) if s is False]
        cells = 3  # sentinel "1Ns"
        vals = []
        for i in singles + pairs:
            vals.append(pack128(phrase_bytes(phr[i][0])))
        used_small = set(list(sorted(SMALL_FREE))[:len(singles)])
        for v in range(1, 17):
            if v in used_small:
                continue
            vals.append(9 if v in SMALL_FREE else pack128(spell(v)))
        for v in vals:
            s = str(v)
            cells += 2 if len(s) == 1 else len(s) + 3
        return cells

    # trim weakest (last-added) pair phrases until the table fits its budget;
    # their refs revert to raw symbols.
    if table_budget:
        while table_cells(phrases) > table_budget:
            # drop the pair phrase with the smallest stream cost (m-2)*t,
            # tie-broken toward the largest table entry
            best = None
            for i, (pat, single) in enumerate(phrases):
                if single is not False or (len(pat) == 1 and pat[0] in STOLEN):
                    continue
                t = count_nonoverlap(stream, (-i - 1,))
                cost = (len(pat) - 2) * t
                entry = len(str(pack128(phrase_bytes(pat)))) + 3
                key = (cost, -entry)
                if best is None or key < best[0]:
                    best = (key, i, pat)
            if best is None:
                raise ValueError("cannot trim table")
            _, i, pat = best
            stream = replace_nonoverlap(stream, (-i - 1,), list(pat))
            phrases[i] = (pat, None)   # dropped marker
    singles = [i for i, (p, s) in enumerate(phrases) if s is True]
    pairs = [i for i, (p, s) in enumerate(phrases) if s is False]
    assert len(singles) <= len(SMALL_FREE)
    ring, slot_of = {}, {}
    for i, v in zip(singles, sorted(SMALL_FREE)):
        slot_of[i] = ("single", v)
        ring[v] = pack128(phrase_bytes(phrases[i][0]))
    for v in range(1, 17):
        if v not in ring:
            ring[v] = 9 if v in SMALL_FREE else pack128(spell(v))

    # --- template layout for P1 group B (pairs), 4 rows x nB slots ---
    # Assign pair values to a grid so every column's backtick count is even
    # and spans stay digit/space-only (oracle vertical-literal rule).
    if tail_constants:
        # Keep the original 19-entry four-row grid.  Its old sentinel cell
        # becomes an unsent filler, while all new constants and the one real
        # sentinel move to the first pump row.
        grid_pairs = pairs[:19]
        tail_pairs = pairs[19:]
        assert len(grid_pairs) == 19
        assert len(tail_pairs) == extra_pair_count
    else:
        grid_pairs = pairs
        tail_pairs = []
    pair_vals = [pack128(phrase_bytes(phrases[i][0])) for i in grid_pairs]
    order = sorted(range(len(pair_vals)),
                   key=lambda i: -len(str(pair_vals[i])))
    nB = (
        -(-len(pair_vals) // 4)
        if tail_constants
        else -(-(len(pair_vals) + 1) // 4)       # +1 for the zero sentinel
    )
    grid = [[None] * nB for _ in range(4)]       # rows 0..3 = P1 rows 3..6
    # widest chunk goes to the physically-last slot; sentinel to slot 0
    chunks_desc = [order[i * 4:(i + 1) * 4] for i in range(nB)]
    widths = []
    for j, chunk in enumerate(chunks_desc):
        widths.append(max(len(str(pair_vals[i])) for i in chunk))
    # physical slot order puts the narrow slot where the sentinel lands, so
    # that row's tail leaves room for the pump: slot 0 for the east-first
    # layouts, slot nB-1 for the west-first one.
    phys = sorted(range(nB), key=lambda j: -widths[j] if west_first
                  else widths[j])
    TB = [widths[j] for j in phys]
    cellgrid = [[None] * nB for _ in range(4)]
    fill = []
    for j, chunk in enumerate(chunks_desc):
        pj = phys.index(j)
        for r, i in enumerate(chunk):
            cellgrid[r][pj] = grid_pairs[i]

    # Position numbering follows the preload walk: row-major, and within a row
    # the direction the little man actually travels.
    def walk(r):
        westward = (r % 2 == 0) if west_first else (r % 2 == 1)
        return range(nB - 1, -1, -1) if westward else range(nB)

    def number(ring):
        posmap, pos = {}, 17
        for r in range(4):
            for pj in walk(r):
                idx = cellgrid[r][pj]
                if idx is None:
                    continue
                posmap[idx] = pos
                ring[pos] = pack128(phrase_bytes(phrases[idx][0]))
                pos += 1
        return posmap, pos

    posmap, pos = number(ring)
    # In the legacy layout the sentinel belongs at the very last preload
    # position: the final cell of row 3 in walk order.  The narrow layout
    # fills that slot and emits its sentinel on the extra eastbound row.
    last_cell = list(walk(3))[-1]
    if not tail_constants and cellgrid[3][last_cell] is not None:
        # find a free cell and move the occupant there
        moved = cellgrid[3][last_cell]
        done = False
        for r in range(4):
            for pj in range(nB):
                if cellgrid[r][pj] is None and not done:
                    assert TB[pj] >= len(str(pack128(phrase_bytes(phrases[moved][0]))))
                    cellgrid[r][pj] = moved
                    done = True
        assert done, "no free cell for sentinel"
        cellgrid[3][last_cell] = None
        ring = {k: v for k, v in ring.items() if k <= 16}
        posmap, pos = number(ring)
    for i in tail_pairs:
        posmap[i] = pos
        ring[pos] = pack128(phrase_bytes(phrases[i][0]))
        pos += 1
    for i in pairs:
        slot_of[i] = ("pair", posmap[i])
    layout = dict(TB=TB, cellgrid=cellgrid,
                  val_of={i: pack128(phrase_bytes(phrases[i][0]))
                          for i in pairs},
                  tail_pairs=tail_pairs)

    symbols = []
    for t in stream:
        if t >= 0:
            symbols.append(t)
        else:
            kind, v = slot_of[-t - 1]
            symbols.extend([v] if kind == "single" else [ESC, v])
    assert all(0 <= s < B1 for s in symbols)
    # 17 may appear only as a pair index right after ESC (read by the ESC
    # lane's r, bypassing the classifier where a bare 17 would be fatal).
    i = 0
    while i < len(symbols):
        s = symbols[i]
        assert s != 17, f"bare 17 at {i}"
        i += 2 if s == ESC else 1
    return symbols, ring, layout


def pack_chunks(symbols, digit_widths):
    # A feeder literal is decimal source text but its numeric value is a
    # little-endian base-92 bundle.  Do not end a bundle with zero: repeated
    # divmod in DECODER would otherwise lose that final zero marker.
    maxsym = 1
    while (B1 ** (maxsym + 1)) < 2 ** 63:
        maxsym += 1
    chunks, i = [], 0
    while i < len(symbols):
        row, slot = divmod(len(chunks), len(digit_widths))
        phys = slot if row % 2 == 0 else len(digit_widths) - 1 - slot
        maxd = digit_widths[phys]
        for count in range(min(maxsym, len(symbols) - i), 0, -1):
            if symbols[i + count - 1] == 0:
                continue
            v = sum(symbols[i + j] * B1 ** j for j in range(count))
            if len(str(v)) <= maxd and int(str(v)[::-1]) < 2 ** 63:
                chunks.append(v); i += count
                break
        else:
            raise ValueError(f"cannot chunk at {i}")
    return chunks


def verify(chunks, ring):
    # This is the semantic counterpart of the grid below.  Keeping it here is
    # important: the room program is densely folded, while this follows the
    # five stages in their logical (rather than spatial) order.
    syms = []
    for c in chunks:
        while c:
            c, r = divmod(c, B1)
            syms.append(r)
    mid, i = [], 0
    while i < len(syms):
        v = syms[i]; i += 1
        if v == 0:
            mid.append(0)
        elif v == ESC:
            mid.append(ring[syms[i]]); i += 1
        elif v <= 16:
            mid.append(ring[v])
        else:
            mid.append(v + 31)
    out_vals, code, bp = [], pack128(f"; {FIRST_YEAR}: ".encode()), 10
    for v in mid:
        if v > 0:
            out_vals.append(v)
        else:
            out_vals.append(code)
            code += STEP
            bp -= 1
            if bp == 0:
                code += CORR; bp = 10
    out = bytearray()
    for v in out_vals:
        while v:
            v, r = divmod(v, B2)
            out.append(r)
    return bytes(out) == TEXT


# ------------------------------------------------------------- room grids --

# DISP is the dispatch/lookup room.  It receives base-92 symbols from
# DECODER.  Ordinary symbols add 31; a zero is forwarded to YEAR; small
# symbols and ESC,pair-index references rotate the P1 ring until the requested
# packed entry is found, emit it, then restore the complete ring (including
# its -1 sentinel) to canonical order.
DISP_ROWS = [
    "v@<<s<<<<<<<<            ",
    ">`17`Mr  X^              ",
    " >`31`+^ -               ",
    "vX~`92`M+X+b >> mdrMs>rv ",
    ">rb          ^^sr<   ^sX ",
    "            ^W        s< ",
]

# The sentinel restore path in DISP_ROWS spends its sixth row only walking
# west from the ring send back to the selected value in B.  At width 81 there
# are four unused columns to the right of the narrow dispatcher.  Route that
# cold path east instead, swap there, and return along the first row.  This
# turns DISP from 26x8 into 30x7 without changing its ports or hot lookup loop.
DISP_FOLDED_ROWS = [
    "v@<<s<<<<<<<<              <",
    ">`17`Mr  X^                 ",
    " >`31`+^ -                  ",
    "vX~`92`M+X+b >> mdrMs>rv    ",
    ">rb          ^^sr<   ^sX sW^",
]

# Repeated /92 emits one least-significant stream symbol per feeder chunk.
DECODER_ROWS = [
    ">W/WsWX@v",
    "^`29`M<r<",
]

# Repeated /128 turns a packed raw-ASCII dictionary/year value into bytes.
UNPACK_ROWS = [
    ">W/Ws WX@v",
    "^`821`M<r<",
]


def year_rows():
    # YEAR stores its next packed "; YYYY: " value in A.  STEP advances five
    # ASCII digits at once; after ten years CORR fixes the decimal carry from
    # 2009 -> 2010 (and again 2019 -> 2020).
    d_init = str(pack128(f"; {FIRST_YEAR}: ".encode()))
    d_step = str(STEP)
    d_corr = str(abs(CORR))
    assert (len(d_init), len(d_step), len(d_corr)) == (17, 11, 12)
    row0 = "@`" + d_init + "`M`10`bv"
    row1 = "v  <" + " " * 19 + "<  <"
    row2 = "   s" + " " * 23
    row3 = list(" " * 27)
    row3[26] = "<"; row3[25] = "`"
    for i, ch in enumerate(d_corr):
        row3[24 - i] = ch
    row3[12] = "`"; row3[11] = "N"; row3[10] = "+"; row3[9] = "M"
    row3[8] = "`"; row3[7] = "1"; row3[6] = "0"; row3[5] = "`"
    row3[4] = "b"; row3[3] = "N"; row3[0] = "v"
    row4 = ">rNXWsM`" + d_step + "`+Mma  ^"
    rows = [row0, "".join(row1), row2, "".join(row3), row4]
    assert all(len(r) == 27 for r in rows)
    return rows


# ---------------------------------------------------------------- builder --

def put_row(program, x, y, cells):
    for dx, glyph in enumerate(cells):
        if glyph != " ":
            program.put(x + dx, y, glyph)


def paste_room(program, x0, y0, rows, w=None, h=None):
    w = w or (max(len(r) for r in rows) + 2)
    h = h or (len(rows) + 2)
    program.room(x0, y0, w, h)
    for dy, row in enumerate(rows):
        put_row(program, x0 + 1, y0 + 1 + dy, row)
    return w, h


def feeder(program, chunks, digit_widths, width):
    # One serpentine walker visits every literal exactly once.  Reversing the
    # decimal digits on westbound rows makes the literal value direction-
    # invariant, so the compact two-dimensional packing preserves stream order.
    slots = len(digit_widths)
    group_widths = [d + 3 for d in digit_widths]
    group_starts = [sum(group_widths[:i]) for i in range(slots)]
    left = 1
    content_left = 2
    right = content_left + sum(group_widths) + 1
    assert right + 2 <= width, (right + 2, width)
    rows = (len(chunks) + slots - 1) // slots
    # vertical tick pairing: every slot column must have an even number of
    # backticks within the feeder, so pad to an even row count
    rows += rows % 2
    for row in range(rows):
        y = row + 1
        east = row % 2 == 0
        for logical_slot in range(slots):
            ci = row * slots + logical_slot
            phys = logical_slot if east else slots - 1 - logical_slot
            digits = digit_widths[phys]
            if ci >= len(chunks):
                # dummy literal (no send) keeps this column's backtick
                # count even for the oracle's vertical pairing rule
                decimal = "0" * digits
                send = " "
            else:
                decimal = str(chunks[ci]).zfill(digits)
                send = "s"
            if east:
                x = content_left + 1 + group_starts[phys]
                cells = ["`", *decimal, "`", send]
            else:
                x = content_left + group_starts[phys]
                cells = [send, "`", *decimal[::-1], "`"]
            put_row(program, x, y, cells)
        if east:
            if row:
                program.put(left, y, ">")
            program.put(right, y, "H" if row == rows - 1 else "v")
        else:
            program.put(right, y, "<")
            program.put(left, y, "H" if row == rows - 1 else "v")
    program.put(left, 1, "@")
    program.room(0, 0, width, rows + 2)
    return rows


def variable_feeder(program, bands: list[Band], width: int):
    """Render a DP-optimized feeder whose slot widths vary by two-row band."""
    left = 1
    content_left = 2
    right = width - 2
    row_base = 0
    for band_index, band in enumerate(bands):
        starts = []
        x = content_left
        for digits in band.widths:
            starts.append(x)
            x += digits + 3
        assert x + 3 <= width, (x + 3, width)

        halves = (band.top,) if band.rows == 1 else (band.top, band.bottom)
        for parity, chunks in enumerate(halves):
            row = row_base + parity
            y = row + 1
            east = parity == 0
            for logical_slot, chunk in enumerate(chunks):
                physical_slot = (
                    logical_slot if east else len(band.widths) - 1 - logical_slot
                )
                digits = band.widths[physical_slot]
                decimal = (
                    str(chunk.value).zfill(digits) if chunk is not None else "0" * digits
                )
                send = "s" if chunk is not None else " "
                if east:
                    slot_x = starts[physical_slot] + 1
                    cells = ["`", *decimal, "`", send]
                else:
                    slot_x = starts[physical_slot]
                    cells = [send, "`", *decimal[::-1], "`"]
                put_row(program, slot_x, y, cells)
            if east:
                if row:
                    program.put(left, y, ">")
                # a lone final row runs out east, so it halts on the right
                program.put(right, y, "H" if band.rows == 1 else "v")
            else:
                program.put(right, y, "<")
                program.put(
                    left,
                    y,
                    "H" if band_index == len(bands) - 1 else "v",
                )
        row_base += band.rows
    program.put(left, 1, "@")
    rows = row_base
    program.room(0, 0, width, rows + 2)
    return rows


def p1_slot_cells(v, width, east):
    """Standard slot rendering: value zfilled to slot width."""
    d = str(v).zfill(width)
    return ["`", *d, "`", "s"] if east else ["s", "`", *d[::-1], "`"]


def p1_room(program, x0, y0, width, ring, layout, west_first=False):
    """Template preload room: 2 group-A rows (smalls 1..16, 8 slots) and
    4 group-B rows, all slot-aligned so every column's backtick count is
    even.  The baseline puts its zero sentinel in group B and its pump at the
    lower left.  The narrow variant fills group B, sends tail constants plus
    the sentinel on row 7, and moves the pump to the lower right.

    ``west_first`` walks W,E,W,E,W,E instead of E,W,E,W,E,W, so the last data
    row ends bottom-*right*.  That lets the pump be a six-cell loop in the two
    columns between the turn column and the right wall rather than two rows of
    its own -- an 8-row room instead of 10.  It is incompatible with
    ``tail_constants``, which needs those rows to carry extra entries."""
    assert not (west_first and layout["tail_pairs"])
    smalls = [ring[v] for v in range(1, 17)]
    szA = [len(str(v)) for v in smalls]
    TA = [max(szA[j], szA[15 - j]) for j in range(8)]
    TB = layout["TB"]
    cellgrid = layout["cellgrid"]
    tail_pairs = layout["tail_pairs"]
    nB = len(TB)
    inner = width - 4
    assert sum(TA) + 3 * 8 <= inner, (sum(TA) + 24, inner)
    if tail_pairs:
        assert sum(TB) + 3 * nB <= inner - 2, (
            sum(TB) + 3 * nB,
            inner,
        )
    else:
        assert sum(TB) + 3 * nB + 4 <= inner + 1, (
            sum(TB) + 3 * nB,
            inner,
        )

    def place_row(y, vals, widths, east):
        # feeder-style alignment: slot pitch w+3; east cells at start+1,
        # west cells at start -> backtick columns coincide across rows
        starts = []
        acc = x0 + 2
        for w in widths:
            starts.append(acc)
            acc += w + 3
        endx = acc
        for j, (v, w) in enumerate(zip(vals, widths)):
            if v is None:
                cells = (
                    ["`", *("0" * w), "`", " "]
                    if east
                    else [" ", "`", *("0" * w), "`"]
                )
            else:
                cells = p1_slot_cells(v, w, east)
            x = starts[j] + 1 if east else starts[j]
            put_row(program, x, y, cells)
        return endx

    # Both bands share one turn column, one past the wider band's last cell
    # (an eastbound row's final 's' sits on that cell, a westbound row's does
    # not, so the eastbound span is the one to clear).
    turn = x0 + 3 + max(sum(w + 3 for w in TA), sum(w + 3 for w in TB))
    if west_first:
        # turn column, two pump columns, right wall
        assert turn + 3 <= x0 + width - 1, (turn, width)

    # Group A rows carry ring positions 1..16.  The row walked first holds
    # 1..8; a westbound row is visited slot 7 first, so its values sit
    # reversed to keep preload order ascending.
    if west_first:
        # slot j now pairs smalls[7-j] with smalls[8+j], so the widths run the
        # other way too
        rows_spec = [(smalls[0:8][::-1], TA[::-1], False),
                     (smalls[8:16], TA[::-1], True)]
    else:
        rows_spec = [(smalls[0:8], TA, True), (smalls[8:16][::-1], TA, False)]
    # Group B contains the multi-symbol phrase entries.  In the baseline its
    # last zero is the sentinel observed by DISP after one full rotation.
    for r in range(4):
        vals = []
        for pj in range(nB):
            idx = cellgrid[r][pj]
            if idx is None:
                # Baseline: the sole empty cell is the sentinel.  Narrow
                # variant: it is an unsent vertical-literal filler.
                vals.append(None if tail_pairs else 0)
            else:
                vals.append(layout["val_of"][idx])
        rows_spec.append((vals, TB, (r % 2 == 1) if west_first else (r % 2 == 0)))
    nrows = len(rows_spec)
    room_h = nrows + 2 if west_first else nrows + 2 + 2
    program.room(x0, y0, width, room_h)
    right = turn if west_first else x0 + width - 2
    for ri, (vals, widths, east) in enumerate(rows_spec):
        y = y0 + 1 + ri
        last = ri == nrows - 1
        endx = place_row(y, vals, widths, east)
        if east:
            if ri:
                program.put(x0 + 1, y, ">")
            if last:
                assert west_first
                # Walk on past the turn column into the pump loop: '^' r '>'
                # up the first spare column, 'v' s '<' down the second, so the
                # first instruction executed on entry is the 'r'.
                program.put(right, y, ">")
                put_row(program, right + 1, y - 2, [">", "v"])
                put_row(program, right + 1, y - 1, ["r", "s"])
                put_row(program, right + 1, y, ["^", "<"])
            else:
                program.put(right, y, "v")
        else:
            program.put(right, y, "<")
            program.put(x0 + 1, y, "v")
            if last and not tail_pairs:
                # descend to the pump rows below the data
                put_row(program, x0 + 1, y + 1, [">", ">", "r", "s", "v"])
                put_row(program, x0 + 1, y + 2, [" ", "^", "<", "<", "<"])
    if tail_pairs:
        # The last data row already descends at the left.  Send the remaining
        # constants eastbound on the first pump row, followed by the sentinel.
        # Matching unsent zero literals below preserve vertical backtick
        # pairing.  The steady `r,s` pump occupies the rightmost five interior
        # cells, leaving the entire preceding span available to constants.
        values = [layout["val_of"][i] for i in tail_pairs] + [0]
        widths = [len(str(v)) for v in values]
        starts = []
        acc = x0 + 2
        for w in widths:
            starts.append(acc)
            acc += w + 3
        pump_x = x0 + width - 6
        assert acc + 1 <= pump_x, (acc, pump_x)
        extra_y = y0 + 1 + nrows
        dummy_y = extra_y + 1
        program.put(x0 + 1, extra_y, ">")
        for start, value, slot_width in zip(starts, values, widths):
            put_row(
                program,
                start + 1,
                extra_y,
                p1_slot_cells(value, slot_width, True),
            )
            dummy = ["`", *("0" * slot_width), "`", " "]
            put_row(program, start + 1, dummy_y, dummy)
        put_row(program, pump_x, extra_y, [">", ">", "r", "s", "v"])
        put_row(program, pump_x, dummy_y, [" ", "^", "<", "<", "<"])
    if west_first:
        # A man spawns facing east, so start him one cell west of the turn
        # column: he steps onto its '<', turns, and walks back over '@'.
        assert program.cells.get((right - 1, y0 + 1)) is None, "no room for @"
        program.put(right - 1, y0 + 1, "@")
    else:
        program.put(x0 + 1, y0 + 1, "@")
    return room_h


def audit_vertical_ticks(program):
    """Oracle rule: consecutive same-column backticks must have only
    digits/spaces between, within one room.  Returns list of (x, ya, yb).

    Room scoping matters: walls terminate literal parsing, so ticks in two
    vertically stacked rooms must never be paired with each other.
    """
    cells = program.cells
    bad = []
    for room in program.rooms:
        for x in range(room.ix0, room.ix1 + 1):
            ticks = [
                y
                for y in range(room.iy0, room.iy1 + 1)
                if cells.get((x, y)) == "`"
            ]
            for i in range(0, len(ticks) - 1, 2):
                a, b = ticks[i], ticks[i + 1]
                for y in range(a + 1, b):
                    c = cells.get((x, y), " ")
                    if not (c.isdigit() or c == " "):
                        bad.append((x, a, b))
                        break
    return bad


def build(W=83, variable=False, compact_tail=False, narrow=False,
          west_first=False):
    assert W >= (81 if (narrow or west_first) else (82 if variable else 83))
    if narrow or west_first:
        if (W, variable, compact_tail) != (81, True, True):
            raise ValueError(
                "the narrow/west-first tails require W=81, variable=True, "
                "compact_tail=True"
            )
        if narrow and west_first:
            raise ValueError("narrow and west_first are alternative tails")
    elif compact_tail and (W != 82 or not variable):
        raise ValueError("the compact 82x82 tail requires W=82 and variable=True")
    symbols, ring, layout = build_encoding(
        extra_pair_count=NARROW_EXTRA_PAIRS if narrow else 0,
        tail_constants=narrow,
        west_first=west_first,
    )
    if variable:
        bands = optimize_feeder(symbols, W)
        chunks = [chunk.value for band in bands for chunk in band.chunks]
        dw = None
    else:
        dw = (18, 18, 18, W - 17 - 54)
        assert dw[3] >= 4
        chunks = pack_chunks(symbols, dw)
        bands = None
    assert verify(chunks, ring), "encoding does not reproduce the text"
    if compact_tail:
        program = build_compact_once(
            W, chunks, ring, layout, bands, narrow=narrow,
            west_first=west_first,
        )
    else:
        program = build_once(W, chunks, dw, ring, layout, bands=bands)
    bad = audit_vertical_ticks(program)
    assert not bad, f"vertical tick audit failed: {bad[:4]}"
    return program


def build_champion():
    """Build the checked-in 81x81 champion."""
    program = build(81, variable=True, compact_tail=True, west_first=True)
    assert program.footprint() == (81, 81, 6561)
    return program


def build_82x82():
    """Build the previous 82x82 champion (still reproduced byte-for-byte)."""
    program = build(82, variable=True, compact_tail=True)
    assert program.footprint() == (82, 82, 6724)
    return program


def build_narrow():
    """Build the constant-tail 81x82 variant."""
    program = build(81, variable=True, compact_tail=True, narrow=True)
    assert program.footprint() == (81, 82, 6724)
    return program


def build_compact_once(W, chunks, ring, layout, bands, narrow=False,
                       west_first=False):
    """Place the optimized feeder and the hand-folded service tail.

    ``west_first`` is the 81x81 tail.  P1 needs 80 columns once its pump moves
    into the margin, so the single column left beside it is a dead end for the
    ring (a pipe cannot turn back in it).  All 35 ring cells therefore live in
    the service band, which means widening the strip east of DISP to five
    columns: every room slides one column left and DISP is trimmed to 26.
    Each room keeps its position *relative* to its own pipe attachments, so
    DISP's nearest-pipe bindings are unchanged."""
    program = Program()
    feeder_rows = variable_feeder(program, bands, W)
    assert feeder_rows == (63 if west_first else 62)
    tail_top = feeder_rows + 2
    assert tail_top == (65 if west_first else 64)

    # Room left edges, and DISP's width.  DISP's last inner column is entirely
    # blank, so 26 columns suffice; that trim is what pays for both narrow
    # layouts.  For west_first it buys the five-column ring strip while still
    # leaving DISP -> YEAR a two-column gap (the loader rejects a one-cell
    # pipe, verified against the oracle).
    xu, xo, xy, xd, xp = ((1, 16, 19, 3, 50) if west_first
                          else (2, 17, 20, 4, 51))
    disp_width = 26 if (narrow or west_first) else None

    # Service rooms occupy the top eight rows of the tail.  P1 is below them,
    # rather than above them as in build_once(), which removes the old gap rows.
    paste_room(program, xu, tail_top, UNPACK_ROWS)
    program.output_room(xo, tail_top)
    yw, yh = paste_room(program, xy, tail_top, year_rows())
    assert (yw, yh) == (29, 7)
    dwid, dh = paste_room(program, xp, tail_top, DISP_ROWS, w=disp_width)
    assert (dwid, dh) == ((26 if (narrow or west_first) else 27), 8)
    paste_room(program, xd, tail_top + 4, DECODER_ROWS)
    p1h = p1_room(program, 0, tail_top + 8, W - 1 if west_first else W - 2,
                  ring, layout, west_first=west_first)
    assert p1h == (8 if west_first else 10)

    # feeder -> DECODER
    program.pipe([(xd - 3, tail_top), (xd - 3, tail_top + 5),
                  (xd - 1, tail_top + 5)])
    # UNPACK -> O
    program.pipe([(xu + 12, tail_top + 1), (xo - 1, tail_top + 1)])
    # DISP -> YEAR
    program.pipe([(xp - 1, tail_top + 1), (xy + 29, tail_top + 1)])
    # YEAR -> UNPACK.  The two adjacent bends are intentional.
    program.pipe([
        (xy - 1, tail_top + 3),
        (xu + 13, tail_top + 3),
        (xu + 13, tail_top + 2),
        (xu + 12, tail_top + 2),
    ])
    # DECODER -> DISP.  Its last cell is a north-to-east corner into DISP.
    # In the west_first tail it shares the gap column with DISP -> YEAR, so it
    # climbs only to row +3 and leaves row +1 to that pipe.
    program.pipe(
        [
            (xd + 11, tail_top + 5),
            (xd + 12, tail_top + 5),
            (xd + 12, tail_top + 7),
            (xp - 1, tail_top + 7),
            (xp - 1, tail_top + (3 if west_first else 2)),
        ],
        end_direction="E",
    )

    if west_first:
        # Both legs snake inside the five-column strip east of DISP:
        # 26 + 13 = 39 cells, over the 35-word capacity floor.
        program.pipe(
            [
                (76, tail_top),
                (80, tail_top),
                (80, tail_top + 7),
                (79, tail_top + 7),
                (79, tail_top + 1),
                (78, tail_top + 1),
                (78, tail_top + 7),
            ],
            end_direction="S",
        )
        program.pipe(
            [
                (77, tail_top + 7),
                (77, tail_top + 1),
                (76, tail_top + 1),
                (76, tail_top + 6),
            ],
            end_direction="W",
        )
        return program

    if narrow:
        # The 38-entry narrow dictionary plus sentinel needs at least 38
        # combined ring cells.  This folded leg has 45 cells: after returning
        # up x79 it folds down x78 above P1, staying inside columns 0..80.
        program.pipe(
            [
                (77, tail_top),
                (80, tail_top),
                (80, tail_top + 17),
                (79, tail_top + 17),
                (79, tail_top + 1),
                (78, tail_top + 1),
                (78, tail_top + 7),
            ],
            end_direction="S",
        )
        # Shrinking DISP by its unused rightmost interior column frees x77 for
        # the minimum return pipe from P1.
        program.pipe(
            [(77, tail_top + 7), (77, tail_top + 6)],
            end_direction="W",
        )
    else:
        # Dictionary ring, at its exact semantic capacity floor: 2 + 33 = 35.
        # DISP -> P1 takes the two outer columns down and back up.  The last
        # cell turns south into P1's top border.
        program.pipe(
            [
                (78, tail_top),
                (81, tail_top),
                (81, tail_top + 17),
                (80, tail_top + 17),
                (80, tail_top + 7),
                (79, tail_top + 7),
            ],
            end_direction="S",
        )
        # P1 -> DISP is the minimum two-cell return; its final cell turns west.
        program.pipe(
            [(78, tail_top + 7), (78, tail_top + 6)],
            end_direction="W",
        )
    return program


def build_once(W, chunks, dw, ring, layout, bands=None):
    program = Program()
    R1 = (
        variable_feeder(program, bands, W)
        if bands is not None
        else feeder(program, chunks, dw, W)
    )
    yf = R1 + 1

    p1y = yf + 1
    p1h = p1_room(program, 2, p1y, W - 2, ring, layout)
    yb = p1y + p1h - 1                 # P1 bottom border row
    g1 = yb + 1
    T = yb + 2                         # bandA top border row

    paste_room(program, 2, T, UNPACK_ROWS)       # x2..13, rows T..T+3
    paste_room(program, 4, T + 4, DECODER_ROWS)  # x4..14, rows T+4..T+7
    program.output_room(17, T)                   # x17..19, rows T..T+2
    yw, yh = paste_room(program, 20, T, year_rows())
    assert (yw, yh) == (29, 7)                   # x20..48
    dwid, dh = paste_room(program, 52, T, DISP_ROWS)
    assert (dwid, dh) == (27, 8)                 # x52..78

    # feeder -> decoder (west margin)
    program.pipe([(1, yf + 1), (1, T + 4), (0, T + 4), (0, T + 5),
                  (3, T + 5)])
    # decoder -> DISP (under year, up the wide year/DISP gap)
    program.pipe([(15, T + 5), (16, T + 5), (16, T + 7), (50, T + 7),
                  (50, T + 2), (51, T + 2)])
    # DISP -> year
    program.pipe([(51, T + 1), (49, T + 1)])
    # year -> unpack
    program.pipe([(19, T + 3), (15, T + 3), (15, T + 2), (14, T + 2)])
    # unpack -> O
    program.pipe([(14, T + 1), (16, T + 1)])
    # ring: drawn manually so the end arrows point into the walls even
    # where program.pipe()'s last-segment rule cannot (single g1 row).
    # DISP -> P1: east wall row3 -> up col 80 -> west along g1 -> north
    program.put(79, T + 4, ">")
    program.put(80, T + 4, "^")
    for y in range(T, T + 4):
        program.put(80, y, "|")
    program.put(80, g1, "<")
    for x in range(17, 80):
        program.put(x, g1, "-")
    program.put(16, g1, "^")
    # P1 -> DISP: south wall col 81 -> down -> into DISP east wall row5
    program.put(81, g1, "v")
    for y in range(T, T + 7):
        program.put(81, y, "|")
    program.put(81, T + 7, "<")
    program.put(80, T + 7, "^")
    program.put(80, T + 6, "<")
    program.put(79, T + 6, "<")
    return program


def main():
    legacy = "--legacy" in sys.argv
    variable = "--variable" in sys.argv
    narrow = "--narrow" in sys.argv
    positional = [
        arg for arg in sys.argv[1:]
        if arg not in ("--legacy", "--variable", "--narrow")
    ]
    if narrow:
        if legacy or variable or positional:
            raise SystemExit("--narrow does not accept other modes or a width")
        program = build_narrow()
        name = os.path.join("candidates", "81x82.man")
    elif legacy:
        if positional == ["82"] and not variable:
            program, name = build_82x82(), os.path.join("best", "82x82.man")
            legacy = False      # best/ files are stored without a final NL
        else:
            W = int(positional[0]) if positional else 83
            program = build(W, variable=variable)
            name = (f"history-ring-variable-{W}.man" if variable
                    else "history-ring.man")
    else:
        if positional or variable:
            raise SystemExit(
                "default build is best/81x81.man; use --legacy 82 for the "
                "previous champion, --narrow for the constant-tail candidate, "
                "or --legacy [W] [--variable] for an older layout"
            )
        program = build_champion()
        name = os.path.join("best", "81x81.man")
    out = os.path.join(HERE, name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(program.render() + ("\n" if legacy else ""))
    w, h, score = program.footprint()
    print(f"wrote {out}: {w}x{h} score={score}")


if __name__ == "__main__":
    main()
