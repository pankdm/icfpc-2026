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
  python3 build_ring.py --feeder79               # 79-wide feeder checkpoint
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
# DISP's classifier threshold: symbols 1..THRESHOLD-1 are ring lookups,
# THRESHOLD is the reserved value (it must never occur in the stream), and
# THRESHOLD+1..91 are literal bytes (+31).  SMALL_FREE lists the symbols below
# it whose byte never occurs, so they are free to carry a dictionary phrase;
# STOLEN lists ones whose byte *does* occur but whose slot we take anyway,
# paying an escape pair for its few occurrences.
THRESHOLD = 17
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
    pairs_left = 91 - THRESHOLD + 1
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


def choose_phrases_weighted(stream, ring_entries=37, table_weight=1.0):
    """Fill a fixed-size dictionary on the symbol/table-width frontier.

    This is the reproducible selector found by ``search_feeder_dictionary.py``.
    Unlike ``choose_phrases``, it keeps the 80x80 ring entry count fixed while
    allowing the source-cell weight to be swept.
    """
    dig1 = math.log10(B1)
    forbidden = set(STOLEN) | {0, ESC}
    remaining = {
        "single": len(SMALL_FREE),
        "pair": ring_entries - (THRESHOLD - 1) - len(STOLEN),
    }
    if remaining["pair"] < 0:
        raise ValueError("ring budget is smaller than the forced entries")
    phrases = []
    for value in STOLEN:
        stream = replace_nonoverlap(
            stream, (value,), [-len(phrases) - 1]
        )
        phrases.append(((value,), False))

    while any(remaining.values()):
        found = {}
        for size in range(2, 10):
            counts = Counter(
                tuple(stream[i:i + size])
                for i in range(len(stream) - size + 1)
                if all(v >= 1 and v not in forbidden
                       for v in stream[i:i + size])
            )
            for phrase, count in counts.items():
                if count < 2 or len(phrase_bytes(phrase)) > 9:
                    continue
                value = pack128(phrase_bytes(phrase))
                if not fits_literal(value) or len(str(value)) > 18:
                    continue
                hits = count_nonoverlap(stream, phrase)
                if hits >= 2:
                    found[phrase] = hits

        best = None
        for phrase, hits in found.items():
            value = pack128(phrase_bytes(phrase))
            table_cells = len(str(value)) + 3
            for kind, slots in remaining.items():
                if not slots:
                    continue
                saving = (
                    len(phrase) - (1 if kind == "single" else 2)
                ) * hits
                if saving <= 0:
                    continue
                score = dig1 * saving - table_weight * table_cells
                key = (
                    score, saving, hits, -table_cells,
                    phrase_bytes(phrase), kind,
                )
                if best is None or key > best[0]:
                    best = (key, phrase, kind)
        if best is None:
            raise ValueError(f"could not fill dictionary slots: {remaining}")
        _, phrase, kind = best
        stream = replace_nonoverlap(
            stream, phrase, [-len(phrases) - 1]
        )
        phrases.append((phrase, kind == "single"))
        remaining[kind] -= 1
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
                   west_first=False, threshold=None, group_b_rows=4,
                   group_a_cap=73, bottom_up=False, phrase_selector=None):
    """``threshold`` is DISP's T: symbols 1..T-1 are ring lookups, T is the
    reserved value, and T+1..91 are literal bytes.  Raising it converts escape
    pairs (2 stream symbols) into direct references (1) at no P1 cost, since a
    promoted entry is already in the ring; the price is that every *used* symbol
    below T needs a cheap packed-byte ring slot.  T must itself be a symbol that
    never occurs."""
    T = THRESHOLD if threshold is None else threshold
    RB = group_b_rows
    selector = choose_phrases if phrase_selector is None else phrase_selector
    stream, phrases = selector(tokenize(TEXT))
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
        for v in range(1, THRESHOLD):
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
    if T == 17:
        # shipped alphabet: keep the historical position order byte-for-byte
        for i, v in zip(singles, sorted(SMALL_FREE)):
            slot_of[i] = ("single", v)
            ring[v] = pack128(phrase_bytes(phrases[i][0]))
        for v in range(1, T):
            if v not in ring:
                ring[v] = 9 if v in SMALL_FREE else pack128(spell(v))
    else:
        # Pin the literal-byte positions, then let pack_group_a() choose which
        # free position each phrase takes so group A's columns pair by width.
        byte_by_pos = {v: pack128(spell(v))
                       for v in range(1, T) if v not in SMALL_FREE}
        phrase_vals = [pack128(phrase_bytes(phrases[i][0])) for i in singles]
        group_a_rows, _, assign = pack_group_a(
            phrase_vals, byte_by_pos, T - 1,
            False if bottom_up else west_first, group_a_cap,
        )
        by_val = {}
        for i in singles:
            by_val.setdefault(pack128(phrase_bytes(phrases[i][0])), []).append(i)
        for pos, val in sorted(assign.items()):
            slot_of[by_val[val].pop()] = ("single", pos)
            ring[pos] = val
        ring.update(byte_by_pos)
        for v in range(1, T):
            ring.setdefault(v, 9)      # unused free position: cheap filler
    if T == 17:
        group_a_rows = 2

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
        -(-len(pair_vals) // RB)
        if tail_constants
        else -(-(len(pair_vals) + 1) // RB)      # +1 for the zero sentinel
    )
    grid = [[None] * nB for _ in range(RB)]
    # widest chunk goes to the physically-last slot; sentinel to slot 0
    chunks_desc = [order[i * RB:(i + 1) * RB] for i in range(nB)]
    widths = []
    for j, chunk in enumerate(chunks_desc):
        # When the phrase count is a multiple of four, the extra legacy
        # sentinel slot creates one otherwise-empty physical group.
        widths.append(
            max((len(str(pair_vals[i])) for i in chunk), default=1)
        )
    # The sentinel must occupy the last cell the preload walk visits, so put
    # the narrowest group there -- that also leaves the row's tail free for the
    # pump.  Which physical slot that is depends on the direction of the last
    # row, i.e. on the parity of the row count, not on west_first alone.
    last_overall_row = group_a_rows + RB - 1
    last_westward = (
        last_overall_row % 2 == 1
        if bottom_up
        else ((last_overall_row % 2 == 0) if west_first
              else (last_overall_row % 2 == 1))
    )
    # westward last row ends on slot 0; eastward ends on slot nB-1
    phys = sorted(range(nB), key=lambda j: widths[j] if last_westward
                  else -widths[j])
    TB = [widths[j] for j in phys]
    cellgrid = [[None] * nB for _ in range(RB)]
    fill = []
    for j, chunk in enumerate(chunks_desc):
        pj = phys.index(j)
        for r, i in enumerate(chunk):
            cellgrid[r][pj] = grid_pairs[i]

    # Position numbering follows the preload walk: row-major, and within a row
    # the direction the little man actually travels.
    def walk(r):
        overall_row = group_a_rows + r
        westward = (
            overall_row % 2 == 1
            if bottom_up
            else ((overall_row % 2 == 0) if west_first
                  else (overall_row % 2 == 1))
        )
        return range(nB - 1, -1, -1) if westward else range(nB)

    def number(ring):
        posmap, pos = {}, T
        for r in range(RB):
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
    last_cell = list(walk(RB - 1))[-1]
    if not tail_constants and cellgrid[RB - 1][last_cell] is not None:
        # Move the occupant to a free cell whose column is wide enough.  The
        # first free cell is not always one -- with the table nearly full the
        # only spare slot can be narrower than the entry being displaced.
        moved = cellgrid[RB - 1][last_cell]
        need = len(str(pack128(phrase_bytes(phrases[moved][0]))))
        done = False
        for r in range(RB):
            for pj in range(nB):
                if cellgrid[r][pj] is None and TB[pj] >= need and not done:
                    cellgrid[r][pj] = moved
                    done = True
        assert done, "no free cell wide enough for the displaced entry"
        cellgrid[RB - 1][last_cell] = None
        ring = {k: v for k, v in ring.items() if k < T}
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
                  tail_pairs=tail_pairs, n_small=T - 1, group_b_rows=RB,
                  group_a_rows=group_a_rows, bottom_up=bottom_up,
                  sentinel_cell=(RB - 1, last_cell))

    symbols = []
    for t in stream:
        if t >= 0:
            symbols.append(t)
        else:
            kind, v = slot_of[-t - 1]
            symbols.extend([v] if kind == "single" else [ESC, v])
    assert all(0 <= s < B1 for s in symbols)
    # The threshold may appear only as a pair index right after ESC (read by
    # the ESC lane's r, bypassing the classifier where a bare T would be fatal).
    i = 0
    while i < len(symbols):
        s = symbols[i]
        assert s != T, f"bare threshold {T} at {i}"
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


def verify(chunks, ring, threshold=None, base=None):
    # This is the semantic counterpart of the grid below.  Keeping it here is
    # important: the room program is densely folded, while this follows the
    # five stages in their logical (rather than spatial) order.
    radix = B1 if base is None else base
    syms = []
    for c in chunks:
        while c:
            c, r = divmod(c, radix)
            syms.append(r)
    mid, i = [], 0
    while i < len(syms):
        v = syms[i]; i += 1
        if v == 0:
            mid.append(0)
        elif v == ESC:
            mid.append(ring[syms[i]]); i += 1
        elif v < (THRESHOLD if threshold is None else threshold):
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


def _grid(width, height, *placements):
    """Index-addressed grid, so a miscounted run of spaces cannot silently
    shift a glyph.  placements are (x, y, text)."""
    cells = [[" "] * width for _ in range(height)]
    for x, y, text in placements:
        for i, glyph in enumerate(text):
            assert cells[y][x + i] == " ", (x + i, y, glyph)
            cells[y][x + i] = glyph
    return ["".join(row) for row in cells]


# The same dispatcher rebuilt at 21x5, used by the 81x81 champion.  It is
# behaviourally identical to DISP_ROWS -- including forwarding a zero marker
# untouched to YEAR -- and three changes pay for the three rows and three
# columns:
#
# * `b` moved up into the head, so the classifier stashes the raw symbol in BP
#   *before* subtracting 17.  The `v <= 16` branch then already holds its
#   rotation count, which deletes the `+`/`b` pair that used to rebuild it from
#   `v - 17`, and lets the ring machinery start two columns earlier.
# * The sentinel test moved ahead of its turn.  Testing the drained value with
#   `X` while still travelling east lets the 0 sentinel leave the drain loop
#   eastward, so `s` (send the sentinel) and `W` (lift the saved entry into A)
#   stack vertically in the last column instead of needing a sixth row to walk
#   west along.
# * The `+31` riser moved from x=7 to the head's free x=7 slot -- `b` sits at
#   x=8 rather than x=7 precisely to keep that column clear.
#
# Ring machinery, x=10..20 of rows 3/4:
#   10..13  rotate BP-1 times: `>` ` ` `m` `d` over `^` `s` `r` `<`
#   14..16  take the wanted entry, keep it in B, put it back on the ring
#   17..19  drain the rest back until the 0 sentinel: `>` `r` `X` over `^` `s` `<`
#   20      sentinel riser: send the sentinel, `W` the entry into A, go home
def disp_compact_rows(threshold=17, esc=29):
    """The 21x5 dispatcher.  Only two constants depend on the alphabet, and
    both are two digits wide, so raising the threshold does not move a single
    cell.  The head's literal is the classifier threshold, read eastward; row
    3's is the ESC value, read *westward*, so its cell content is str(esc)
    reversed.
    """
    assert 10 <= threshold <= 99 and 10 <= esc <= 99, (threshold, esc)
    thr, e = str(threshold), str(esc)[::-1]
    return _grid(21, 5,
        (0, 0, "v@<<s"), (7, 0, "<"), (10, 0, "<"), (20, 0, "<"),
        (0, 1, f">`{thr}`Mr"), (8, 1, "bX^"), (20, 1, "W"),
        (1, 2, ">`31`+^"), (9, 2, "-"), (20, 2, "s"),
        (0, 3, f"vX~`{e}`M+X> mdrMs>rX^"),
        (0, 4, ">rb"), (10, 4, "^sr<"), (17, 4, "^s<"),
    )


DISP_COMPACT_ROWS = disp_compact_rows()


def disp_stream_rows(threshold=23, esc=29):
    """21x5 dispatcher for a regenerating one-way dictionary stream."""
    assert 10 <= threshold <= 99 and 10 <= esc <= 99, (threshold, esc)
    thr, e = str(threshold), str(esc)[::-1]
    return _grid(21, 5,
        (0, 0, "v@<<s"), (7, 0, "<"), (10, 0, "<"), (20, 0, "<"),
        (0, 1, f">`{thr}`Mr"), (8, 1, "bX^"),
        (1, 2, ">`31`+^"), (9, 2, "-"),
        (0, 3, f"vX~`{e}`M+X>rX>rmd   ^"),
        # ESC's next position must come from DECODER, while the scanner uses
        # the nearer dictionary stream.  `R` selects DECODER first in reading
        # order when both are ready; the encoded position is adjacent to ESC.
        (0, 4, ">Rb"), (10, 4, "^ <^  <"),
    )


def decoder_rows(radix=B1):
    """Repeated division emits one least-significant stream symbol per chunk."""
    spelling = str(radix)[::-1]
    assert len(spelling) == 2
    return [">W/WsWX@v", f"^`{spelling}`M<r<"]


DECODER_ROWS = decoder_rows()

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


def group_a_columns(n_small, nA, west_first):
    """position -> physical slot column, following the preload serpentine."""
    RA = -(-n_small // nA)
    col, pos = {}, 0
    for r in range(RA):
        westward = (r % 2 == 0) if west_first else (r % 2 == 1)
        for pj in (range(nA - 1, -1, -1) if westward else range(nA)):
            pos += 1
            if pos <= n_small:
                col[pos] = pj
    return RA, col


def pack_group_a(phrase_vals, byte_by_pos, n_small, west_first, cap):
    """Choose group A's shape *and* which free position each phrase takes.

    Positions that spell a literal byte are pinned (DISP reaches position v for
    symbol v), but the phrases may be permuted among the free positions -- the
    same trick as LOGICAL_ORDER in build_vertical_p1.py.  This matters a lot:
    left in selection order the wide phrase entries and the narrow byte entries
    interleave, every column's slot is as wide as the widest thing the walk
    drops in it, and group A needs five rows instead of three.

    Widths are handed out widest-first to the columns with the most free slots,
    so the wide entries share columns rather than each inflating its own.
    Returns (RA, nA, {position: value}) with the fewest rows.
    """
    free_all = [p for p in range(1, n_small + 1) if p not in byte_by_pos]
    assert len(free_all) >= len(phrase_vals), (len(free_all), len(phrase_vals))
    best = None
    for nA in range(1, n_small + 1):
        RA, col = group_a_columns(n_small, nA, west_first)
        base = [1] * nA
        for p, v in byte_by_pos.items():
            base[col[p]] = max(base[col[p]], len(str(v)))
        slots = {}
        for p in free_all:
            slots.setdefault(col[p], []).append(p)
        vals = sorted(phrase_vals, key=lambda v: -len(str(v)))
        assign, k = {}, 0
        for c in sorted(slots, key=lambda c: -len(slots[c])):
            for pp in slots[c]:
                if k < len(vals):
                    assign[pp] = vals[k]
                    k += 1
        TA = list(base)
        for pp, v in assign.items():
            TA[col[pp]] = max(TA[col[pp]], len(str(v)))
        if sum(TA) + 3 * nA <= cap and (best is None or (RA, nA) < best[:2]):
            best = (RA, nA, assign)
    if best is None:
        raise ValueError(f"group A ({n_small} positions) does not fit cap {cap}")
    return best


def group_a_grid(smalls, west_first, inner):
    """Lay ring positions 1..len(smalls) into RA rows x nA slots.

    Group A is *position*-ordered, not width-ordered: the preload walk must
    visit position 1, 2, 3 ... in order, because DISP reaches position p by
    rotating the ring p-1 times.  So unlike group B this cannot sort by width;
    a column's slot is simply as wide as the widest entry the walk drops in it.
    (The encoder can still permute which phrase lands on which *free* position
    to make those columns pair well -- see LOGICAL_ORDER in
    build_vertical_p1.py.  Positions that spell a literal byte are pinned.)

    Returns (grid, TA, RA, nA), preferring the fewest rows and then the fewest
    slots, which reproduces the hand-written 2x8 layout when len(smalls) == 16.
    """
    n = len(smalls)
    best = None
    for nA in range(1, n + 1):
        RA = -(-n // nA)
        grid = [[None] * nA for _ in range(RA)]
        pos = 0
        for r in range(RA):
            westward = (r % 2 == 0) if west_first else (r % 2 == 1)
            for pj in (range(nA - 1, -1, -1) if westward else range(nA)):
                if pos < n:
                    grid[r][pj] = smalls[pos]
                    pos += 1
        TA = [
            max((len(str(grid[r][j])) for r in range(RA)
                 if grid[r][j] is not None), default=1)
            for j in range(nA)
        ]
        if sum(TA) + 3 * nA > inner:
            continue
        if best is None or (RA, nA) < (best[2], best[3]):
            best = (grid, TA, RA, nA)
    if best is None:
        raise ValueError(f"group A ({n} entries) does not fit width {inner + 4}")
    return best


def p1_room(program, x0, y0, width, ring, layout, west_first=False,
            cyclic_stream=False):
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
    assert not cyclic_stream or west_first
    n_small = layout.get("n_small", 16)
    bottom_up = layout.get("bottom_up", False)
    smalls = [ring[v] for v in range(1, n_small + 1)]
    # west_first must also clear the turn column and the two pump columns, so
    # its usable span is three cells shorter than the plain interior.
    gridA, TA, RA, nA = group_a_grid(
        smalls, False if bottom_up else west_first,
        width - 4 - (3 if (west_first or bottom_up) else 0))
    assert RA == layout.get("group_a_rows", RA)
    TB = layout["TB"]
    cellgrid = layout["cellgrid"]
    tail_pairs = layout["tail_pairs"]
    nB = len(TB)
    inner = width - 4
    assert sum(TA) + 3 * nA <= inner, (sum(TA) + 3 * nA, inner)
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

    # Group A rows carry ring positions 1..n_small in preload-walk order;
    # group_a_grid() has already placed them, so each row is just its physical
    # slot contents plus the direction the walk takes through it.
    rows_spec = []
    for r in range(RA):
        westward = (
            r % 2 == 1
            if bottom_up
            else ((r % 2 == 0) if west_first else (r % 2 == 1))
        )
        rows_spec.append((gridA[r], TA, not westward))
    # Group B contains the multi-symbol phrase entries.  In the baseline its
    # last zero is the sentinel observed by DISP after one full rotation.
    for r in range(layout.get("group_b_rows", 4)):
        vals = []
        for pj in range(nB):
            idx = cellgrid[r][pj]
            if idx is None:
                # Exactly one empty cell is the sentinel.  Smaller row counts
                # can leave additional holes; those are unsent literal fillers
                # and must not inject extra zeroes into the ring.
                vals.append(
                    0
                    if not tail_pairs
                    and (r, pj) == layout.get("sentinel_cell")
                    else None
                )
            else:
                vals.append(layout["val_of"][idx])
        overall_row = RA + r
        east = (
            overall_row % 2 == 0
            if bottom_up
            else ((overall_row % 2 == 1) if west_first
                  else (overall_row % 2 == 0))
        )
        rows_spec.append((vals, TB, east))
    nrows = len(rows_spec)
    room_h = nrows + 2 if (west_first or bottom_up) else nrows + 2 + 2
    program.room(x0, y0, width, room_h)
    right = turn if west_first else x0 + width - 2
    if bottom_up:
        right = turn
        assert right + 3 <= x0 + width - 2, (right, width)
        for ri, (vals, widths, east) in enumerate(rows_spec):
            assert east == (ri % 2 == 0)
            y = y0 + nrows - ri
            place_row(y, vals, widths, east)
            last = ri == nrows - 1
            if east:
                if ri:
                    program.put(x0 + 1, y, ">")
                program.put(right, y, ">" if last else "^")
            else:
                program.put(right, y, "<")
                program.put(x0 + 1, y, "^")
        # The final preload row is the top row and runs east.  Continue into
        # a six-cell pump in the otherwise-dead three-column right margin.
        put_row(program, right + 1, y0 + 1, [">", "r", "v"])
        put_row(program, right + 1, y0 + 2, ["^", "s", "<"])
        program.put(x0 + 1, y0 + nrows, "@")
        return room_h

    for ri, (vals, widths, east) in enumerate(rows_spec):
        y = y0 + 1 + ri
        last = ri == nrows - 1
        endx = place_row(y, vals, widths, east)
        if east:
            if ri:
                program.put(x0 + 1, y, ">")
            if last:
                assert west_first
                program.put(right, y, ">")
                if cyclic_stream:
                    # Rise in one spare column and traverse every literal
                    # again.  The dispatcher resynchronizes on the sentinel.
                    program.put(right + 1, y, "^")
                    program.put(right + 1, y0 + 1, "<")
                else:
                    # Walk on past the turn column into the pump loop: '^' r
                    # '>' up the first spare column, 'v' s '<' down the second.
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
          west_first=False, bottom_up=False, feeder_width=None,
          phrase_selector=None, group_b_rows=4):
    assert not (west_first and bottom_up)
    compact_p1 = west_first or bottom_up
    feeder_width = W if feeder_width is None else feeder_width
    assert feeder_width <= W
    assert W >= (79 if compact_p1 else 81 if narrow else 82 if variable else 83)
    if narrow or compact_p1:
        allowed = (79, 80, 81) if compact_p1 else (81,)
        if (W not in allowed) or not (variable and compact_tail):
            raise ValueError(
                "the narrow/west-first tails require variable=True, "
                f"compact_tail=True and W in {allowed}"
            )
        if narrow and west_first:
            raise ValueError("narrow and west_first are alternative tails")
    elif compact_tail and (W != 82 or not variable):
        raise ValueError("the compact 82x82 tail requires W=82 and variable=True")
    symbols, ring, layout = build_encoding(
        extra_pair_count=NARROW_EXTRA_PAIRS if narrow else 0,
        tail_constants=narrow,
        west_first=west_first,
        bottom_up=bottom_up,
        phrase_selector=phrase_selector,
        group_a_cap=W - 7 if compact_p1 else 73,
        group_b_rows=group_b_rows,
    )
    if variable:
        bands = optimize_feeder(symbols, feeder_width)
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
            west_first=compact_p1, feeder_width=feeder_width,
        )
    else:
        program = build_once(W, chunks, dw, ring, layout, bands=bands)
    bad = audit_vertical_ticks(program)
    assert not bad, f"vertical tick audit failed: {bad[:4]}"
    return program


def free_symbols():
    """Symbol values whose byte never occurs in the text, so they are free to
    carry a dictionary phrase instead of a literal byte."""
    used = set(t for t in tokenize(TEXT) if t > 0)
    return [v for v in range(1, B1) if v not in used]


class alphabet:
    """Temporarily rebind the classifier alphabet.

    THRESHOLD, ESC, SMALL_FREE and STOLEN are module globals because
    choose_phrases() consults them while selecting the dictionary; this rebinds
    them consistently for one build and restores them afterwards.
    """

    def __init__(self, threshold, esc):
        free = free_symbols()
        assert threshold in free, f"threshold {threshold} occurs in the text"
        assert esc in free and esc > threshold, f"bad ESC {esc}"
        self.new = (
            threshold, esc,
            sorted([v for v in free if v < threshold] + [8]),
            (8,),
        )

    def __enter__(self):
        global THRESHOLD, ESC, SMALL_FREE, STOLEN
        self.old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
        THRESHOLD, ESC, SMALL_FREE, STOLEN = self.new
        return self

    def __exit__(self, *exc):
        global THRESHOLD, ESC, SMALL_FREE, STOLEN
        THRESHOLD, ESC, SMALL_FREE, STOLEN = self.old
        return False


def build_80x80():
    """Build the 80x80 stolen-threshold champion.

    Positions 17..22 carry six additional one-symbol phrases.  Symbol 18 is
    the only used byte in that range, and 23 is the classifier threshold; both
    raw bytes are escaped into the ring.  This preserves the proven 21x5 DISP
    shape (only its threshold literal changes), while producing the same
    61-row feeder and 37-entry ring as the much larger Route-B range tester.

    Group A takes three rows and group B four.  Their odd seven-row total is
    preloaded bottom-to-top so the last row runs east into an in-room pump.
    """
    global THRESHOLD, ESC, SMALL_FREE, STOLEN
    old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
    THRESHOLD = 23
    ESC = 29
    SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    STOLEN = (8, 18, 23)
    try:
        program = build(
            80, variable=True, compact_tail=True, bottom_up=True,
        )
    finally:
        THRESHOLD, ESC, SMALL_FREE, STOLEN = old
    assert program.footprint() == (80, 80, 6400)
    return program


def build_feeder79():
    """Regenerate the 80x80 encoding in a 79-column feeder.

    The proven service and seven-row dictionary tail deliberately remain
    80 columns wide.  This is the working geometry checkpoint for the 79x79
    search: only feeder packing changes.  The exact DP jumps from 61 to 63
    feeder rows at this width, so the expected footprint is 80x82.
    """
    global THRESHOLD, ESC, SMALL_FREE, STOLEN
    old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
    THRESHOLD = 23
    ESC = 29
    SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    STOLEN = (8, 18, 23)
    try:
        program = build(
            80, variable=True, compact_tail=True, bottom_up=True,
            feeder_width=79,
        )
    finally:
        THRESHOLD, ESC, SMALL_FREE, STOLEN = old
    assert program.footprint() == (80, 82, 6724)
    return program


def build_feeder79_v2():
    """The fixed-dictionary search winner rendered in the 79-wide feeder."""
    global THRESHOLD, ESC, SMALL_FREE, STOLEN
    old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
    THRESHOLD = 23
    ESC = 29
    SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    STOLEN = (8, 18, 23)
    try:
        program = build(
            80, variable=True, compact_tail=True, bottom_up=True,
            feeder_width=79,
            phrase_selector=choose_phrases_weighted,
        )
    finally:
        THRESHOLD, ESC, SMALL_FREE, STOLEN = old
    assert program.footprint() == (80, 82, 6724)
    return program


def build_79wide_v2():
    """Fit the searched v2 feeder and unchanged seven-row table in width 79."""
    global THRESHOLD, ESC, SMALL_FREE, STOLEN
    old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
    THRESHOLD = 23
    ESC = 29
    SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    STOLEN = (8, 18, 23)
    try:
        program = build(
            79, variable=True, compact_tail=True, bottom_up=True,
            phrase_selector=choose_phrases_weighted,
        )
    finally:
        THRESHOLD, ESC, SMALL_FREE, STOLEN = old
    return program


def build_79x81():
    """Trade a little compression for a six-row dictionary at width 79."""
    global THRESHOLD, ESC, SMALL_FREE, STOLEN
    old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
    THRESHOLD = 23
    ESC = 29
    SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    STOLEN = (8, 18, 23)
    selector = lambda stream: choose_phrases_weighted(
        stream, table_weight=1.25
    )
    try:
        program = build(
            79, variable=True, compact_tail=True, west_first=True,
            phrase_selector=selector, group_b_rows=3,
        )
    finally:
        THRESHOLD, ESC, SMALL_FREE, STOLEN = old
    assert program.footprint() == (79, 81, 6561)
    return program


def build_streaming_79x81():
    """End-to-end checkpoint for the regenerating dictionary stream.

    This deliberately keeps the proven eight-row service placement.  Its
    purpose is to validate the new one-way dictionary protocol on the real
    History Lesson program before reflowing those rooms into seven rows.
    """
    global THRESHOLD, ESC, SMALL_FREE, STOLEN
    old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
    THRESHOLD = 23
    ESC = 29
    SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    STOLEN = (8, 18, 23)
    selector = lambda stream: choose_phrases_weighted(
        stream, table_weight=1.25
    )
    try:
        symbols, ring, layout = build_encoding(
            west_first=True,
            phrase_selector=selector,
            group_b_rows=3,
            group_a_cap=72,
        )
        bands = optimize_feeder(symbols, 79)
        chunks = [chunk.value for band in bands for chunk in band.chunks]
        assert verify(chunks, ring)
        program = build_streaming_once(79, ring, layout, bands)
    finally:
        THRESHOLD, ESC, SMALL_FREE, STOLEN = old
    assert program.footprint() == (79, 81, 6561)
    return program


def build_streaming_squeezed(squeeze=1, weight=1.25):
    """Same machine as 79x80-stream with DISP pulled `squeeze` columns west."""
    global THRESHOLD, ESC, SMALL_FREE, STOLEN
    old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
    THRESHOLD = 23
    ESC = 29
    SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    STOLEN = (8, 18, 23)
    W = 79 - squeeze
    selector = lambda stream: choose_phrases_weighted(stream, table_weight=weight)
    try:
        symbols, ring, layout = build_encoding(
            west_first=True, phrase_selector=selector,
            group_b_rows=3, group_a_cap=72)
        bands = optimize_feeder(symbols, W)
        chunks = [chunk.value for band in bands for chunk in band.chunks]
        assert verify(chunks, ring)
        program = build_streaming_seven_once(W, ring, layout, bands,
                                             squeeze=squeeze)
    finally:
        THRESHOLD, ESC, SMALL_FREE, STOLEN = old
    return program


def build_streaming_79x80():
    """Pack the cyclic dictionary protocol into a seven-row service band."""
    global THRESHOLD, ESC, SMALL_FREE, STOLEN
    old = (THRESHOLD, ESC, SMALL_FREE, STOLEN)
    THRESHOLD = 23
    ESC = 29
    SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    STOLEN = (8, 18, 23)
    selector = lambda stream: choose_phrases_weighted(
        stream, table_weight=1.25
    )
    try:
        symbols, ring, layout = build_encoding(
            west_first=True,
            phrase_selector=selector,
            group_b_rows=3,
            group_a_cap=72,
        )
        bands = optimize_feeder(symbols, 79)
        chunks = [chunk.value for band in bands for chunk in band.chunks]
        assert verify(chunks, ring)
        program = build_streaming_seven_once(79, ring, layout, bands)
    finally:
        THRESHOLD, ESC, SMALL_FREE, STOLEN = old
    assert program.footprint() == (79, 80, 6400)
    return program


def build_champion():
    """Build the checked-in 81x81 champion."""
    program = build(81, variable=True, compact_tail=True, west_first=True)
    assert program.footprint() == (81, 81, 6561)
    return program


def build_w80():
    """Width-80 baseline: the same west_first tail with a width-80 feeder.

    Only useful as a starting point for an 80x80 build.  The feeder DP costs
    one extra row at width 80 (64 content rows rather than 63), so the naive
    packing is 66 feeder + 8 service + 8 P1 = 82 rows, i.e. score 6724 against
    the 81x81 champion's 6561.  Two rows have to come out of the service band
    or P1 before this beats the champion."""
    program = build(80, variable=True, compact_tail=True, west_first=True)
    assert program.footprint() == (80, 82, 6724), program.footprint()
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
                       west_first=False, feeder_width=None):
    """Place the optimized feeder and the hand-folded service tail.

    ``west_first`` is the 81x81 tail.  P1 needs 80 columns once its pump moves
    into the margin, so the single column left beside it is a dead end for the
    ring (a pipe cannot turn back in it).  All 35 ring cells therefore live in
    the service band, which means widening the strip east of DISP to five
    columns: every room slides one column left and DISP is trimmed to 26.
    Each room keeps its position *relative* to its own pipe attachments, so
    DISP's nearest-pipe bindings are unchanged."""
    program = Program()
    feeder_width = W if feeder_width is None else feeder_width
    feeder_rows = variable_feeder(program, bands, feeder_width)
    if THRESHOLD == 17:          # the shipped alphabet; pins the known builds
        assert feeder_rows == ((63 if W == 81 else 64) if west_first else 62)
    tail_top = feeder_rows + 2

    # Room left edges, and DISP's width.  DISP's last inner column is entirely
    # blank, so 26 columns suffice; that trim is what pays for both narrow
    # layouts.  For west_first it buys the five-column ring strip while still
    # leaving DISP -> YEAR a two-column gap (the loader rejects a one-cell
    # pipe, verified against the oracle).
    xu, xo, xy, xd, xp = ((1, 16, 19, 3, 50) if west_first
                          else (2, 17, 20, 4, 51))
    # west_first takes the rebuilt 21x5 dispatcher (DISP_COMPACT_ROWS); the
    # other tails keep the 6-row grid, which is why disp_width still applies.
    disp_rows = (disp_compact_rows(THRESHOLD, ESC) if west_first
                 else DISP_ROWS)
    disp_width = 26 if narrow else None

    # Service rooms occupy the top eight rows of the tail.  P1 is below them,
    # rather than above them as in build_once(), which removes the old gap rows.
    paste_room(program, xu, tail_top, UNPACK_ROWS)
    program.output_room(xo, tail_top)
    yw, yh = paste_room(program, xy, tail_top, year_rows())
    assert (yw, yh) == (29, 7)
    dwid, dh = paste_room(program, xp, tail_top, disp_rows, w=disp_width)
    assert (dwid, dh) == ((23, 7) if west_first
                          else ((26 if narrow else 27), 8))
    paste_room(program, xd, tail_top + 4, DECODER_ROWS)
    # P1's group-B row needs exactly 80 columns (sum(TB) + 3*nB + 4 <= inner+1
    # is tight at inner=76), so west_first always gives it 80 -- which at W=81
    # leaves one dead column beside it and at W=80 is the whole width.
    p1h = p1_room(program, 0, tail_top + 8, W if west_first else W - 2,
                  ring, layout, west_first=west_first)
    if THRESHOLD == 17:
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
        # Both legs snake in the strip east of DISP, which runs from x=73 (the
        # rebuilt dispatcher's east wall is at x=72, so both legs attach
        # squarely to it rather than to the old room corner) out to the right
        # margin.  39 cells at W=81, 37 at W=80, against a 35-word floor.
        e = W - 1                       # rightmost usable column
        program.pipe(
            [
                (73, tail_top + 1),
                (e, tail_top + 1),
                (e, tail_top + 7),
                (e - 1, tail_top + 7),
                (e - 1, tail_top + 2),
                (e - 2, tail_top + 2),
                (e - 2, tail_top + 7),
            ],
            end_direction="S",
        )
        # The return leg's length is a *correctness* requirement, not a
        # preference: the two legs together must hold every ring word but one
        # (see "Pipe-length requirements").  A wider direct range makes the
        # ring longer, so comb the whole remaining strip rather than taking the
        # short route.
        if len(ring) + 1 <= 36:
            back = [(e - 3, tail_top + 7), (e - 3, tail_top + 2),
                    (e - 4, tail_top + 2), (e - 4, tail_top + 5),
                    (73, tail_top + 5)]
        else:
            # Leave P1's top wall immediately, then comb one row above it.
            # Returning to row +7 in another column makes every such cell a
            # second P1 attachment, silently splitting this into parallel
            # pipes and stranding most of the ring in the full first leg.
            back = [(e - 3, tail_top + 7), (e - 3, tail_top + 2),
                    (e - 4, tail_top + 2), (e - 4, tail_top + 6),
                    (e - 5, tail_top + 6), (e - 5, tail_top + 2)]
            if e - 5 != 73:
                back.append((73, tail_top + 2))
        program.pipe(back, end_direction="W")
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


def build_streaming_once(W, ring, layout, bands):
    """Place the cyclic dictionary checkpoint in the proven service layout."""
    program = Program()
    feeder_rows = variable_feeder(program, bands, W)
    tail_top = feeder_rows + 2
    xu, xo, xy, xd, xp = 1, 16, 19, 3, 50

    paste_room(program, xu, tail_top, UNPACK_ROWS)
    program.output_room(xo, tail_top)
    paste_room(program, xy, tail_top, year_rows())
    paste_room(program, xp, tail_top, disp_stream_rows(THRESHOLD, ESC))
    paste_room(program, xd, tail_top + 4, DECODER_ROWS)
    p1_room(
        program, 0, tail_top + 8, W, ring, layout,
        west_first=True, cyclic_stream=True,
    )

    # The four non-dictionary channels retain their proven routes.
    program.pipe([(xd - 3, tail_top), (xd - 3, tail_top + 5),
                  (xd - 1, tail_top + 5)])
    program.pipe([(xu + 12, tail_top + 1), (xo - 1, tail_top + 1)])
    program.pipe([(xp - 1, tail_top + 1), (xy + 29, tail_top + 1)])
    program.pipe([
        (xy - 1, tail_top + 3),
        (xu + 13, tail_top + 3),
        (xu + 13, tail_top + 2),
        (xu + 12, tail_top + 2),
    ])
    program.pipe(
        [
            (xd + 11, tail_top + 5),
            (xd + 12, tail_top + 5),
            (xd + 12, tail_top + 7),
            (xp - 1, tail_top + 7),
            (xp - 1, tail_top + 3),
        ],
        end_direction="E",
    )

    # P1 now regenerates entries, so only a short one-way stream is needed.
    # Leave its top wall immediately to avoid accidental parallel attachments.
    program.pipe(
        [
            (W - 4, tail_top + 7),
            (W - 4, tail_top + 2),
            (73, tail_top + 2),
            (73, tail_top + 5),
        ],
        end_direction="W",
    )
    return program


def build_streaming_seven_once(W, ring, layout, bands, radix=B1, squeeze=0):
    """Seven-row service reflow made possible by the capacity-free dictionary."""
    program = Program()
    feeder_rows = variable_feeder(program, bands, W)
    y = feeder_rows + 2

    # Width accounting is exact: 12 + 1 + 29 + 11 + 3 + 23 = 79.
    xu, xy, xd, xp = 0, 13, 42, 56 - squeeze
    g = 55 - squeeze          # last column of the DECODER/DISP gap
    paste_room(program, xu, y, UNPACK_ROWS)
    paste_room(program, xy, y, year_rows())
    paste_room(program, xd, y, decoder_rows(radix))
    paste_room(program, xp, y, disp_stream_rows(THRESHOLD, ESC))
    program.output_room(4, y + 4)
    p1_room(
        program, 0, y + 7, W, ring, layout,
        west_first=True, cyclic_stream=True,
    )

    # feeder -> DECODER: leave the feeder wall southward, then approach the
    # decoder's right wall from the middle column of the three-column gap.
    program.pipe(
        [(54, y), (54, y + 1), (53, y + 1)],
        end_direction="W",
    )
    # DECODER -> DISP crosses the same gap one row lower.
    program.pipe([(53, y + 2), (g, y + 2)], end_direction="E")
    # DISP -> YEAR leaves west, drops below the short decoder, and enters the
    # year's right wall without crossing either decoder channel.
    program.pipe(
        [
            (g, y + 3), (53, y + 3),
            (53, y + 4), (42, y + 4),
        ],
        end_direction="W",
    )
    # YEAR -> UNPACK uses the one-column room gap and the unpacker's lower
    # right corner; x=11 is below the corner, so only x=10 attaches.
    program.pipe([(12, y + 4), (10, y + 4)], end_direction="N")
    # UNPACK -> O drops away from the bottom wall before turning west.
    program.pipe(
        [(8, y + 4), (8, y + 5), (7, y + 5)],
        end_direction="W",
    )
    # Cyclic P1 -> DISP.  The first step is north, directly away from P1's
    # top wall; the endpoint is closest to the scanner receives, not the head.
    program.pipe(
        ([(54, y + 6), (54, y + 4), (55, y + 4)] if not squeeze
         else [(54, y + 6), (54, y + 4)]),
        end_direction="E",
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
    w80 = "--w80" in sys.argv
    best80 = "--80x80" in sys.argv
    feeder79 = "--feeder79" in sys.argv
    feeder79_v2 = "--feeder79-v2" in sys.argv
    width79_v2 = "--79wide-v2" in sys.argv
    best79 = "--79x81" in sys.argv
    squeeze = next((int(a.split("=")[1]) for a in sys.argv
                    if a.startswith("--squeeze=")), None)
    if squeeze is not None:
        wt = next((float(a.split("=")[1]) for a in sys.argv
                   if a.startswith("--weight=")), 1.25)
        prog = build_streaming_squeezed(squeeze, wt)
        w, h, sc = prog.footprint()
        out = os.path.join(HERE, "candidates",
                           f"squeeze{squeeze}-w{wt}-{w}x{h}.man")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w").write(prog.render())
        print(f"wrote {out}: {w}x{h} score={sc}")
        raise SystemExit(0)
    stream79 = "--79x80-stream" in sys.argv
    positional = [
        arg for arg in sys.argv[1:]
        if arg not in (
            "--legacy", "--variable", "--narrow", "--w80", "--80x80",
            "--feeder79", "--feeder79-v2",
            "--79wide-v2",
            "--79x81",
            "--79x80-stream",
        )
    ]
    if stream79:
        if (
            legacy or variable or narrow or w80 or best80 or best79
            or feeder79 or feeder79_v2 or width79_v2 or positional
        ):
            raise SystemExit(
                "--79x80-stream does not accept other modes or a width"
            )
        program = build_streaming_79x80()
        name = os.path.join("candidates", "79x80-stream.man")
    elif best79:
        if (
            legacy or variable or narrow or w80 or best80
            or feeder79 or feeder79_v2 or width79_v2 or positional
        ):
            raise SystemExit("--79x81 does not accept other modes or a width")
        program = build_79x81()
        name = os.path.join("candidates", "79x81.man")
    elif width79_v2:
        if (
            legacy or variable or narrow or w80 or best80
            or feeder79 or feeder79_v2 or positional
        ):
            raise SystemExit("--79wide-v2 does not accept other modes or a width")
        program = build_79wide_v2()
        name = os.path.join("candidates", "79wide-v2.man")
    elif feeder79_v2:
        if legacy or variable or narrow or w80 or best80 or feeder79 or positional:
            raise SystemExit("--feeder79-v2 does not accept other modes or a width")
        program = build_feeder79_v2()
        name = os.path.join("candidates", "feeder79-v2.man")
    elif feeder79:
        if legacy or variable or narrow or w80 or best80 or positional:
            raise SystemExit("--feeder79 does not accept other modes or a width")
        program = build_feeder79()
        name = os.path.join("candidates", "feeder79-v1.man")
    elif best80:
        if legacy or variable or narrow or w80 or positional:
            raise SystemExit("--80x80 does not accept other modes or a width")
        program = build_80x80()
        name = os.path.join("best", "80x80.man")
    elif w80:
        if legacy or variable or narrow or positional:
            raise SystemExit("--w80 does not accept other modes or a width")
        program = build_w80()
        name = os.path.join("candidates", "80x82.man")
    elif narrow:
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
                "previous champion, --80x80 for the stolen-threshold champion, "
                "--feeder79 for the 79-column feeder checkpoint, "
                "--feeder79-v2 for the fixed-dictionary search winner, "
                "--79wide-v2 for the width-79 layout workbench, "
                "--79x81 for the six-row dictionary layout, "
                "--79x80-stream for the cyclic-dictionary service reflow, "
                "--narrow for the constant-tail candidate, "
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
