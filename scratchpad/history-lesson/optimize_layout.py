#!/usr/bin/env python3
"""Joint optimizer: which phrase tokens to use, and what feeder/tail geometry.

The box score is max(W, H)**2, and the two dimensions pull against each other:

  H = rows + 2 + T     rows shrinks as we tokenize more phrases out of the
                       feeder, but each phrase needs a room in the tail
  W = max(W_feeder, W_tail)
      W_feeder = sum(digit_widths) + 17
      W_tail   = year(28) + decoder/unpack/comma/restorer(42) + 25 per phrase
                 + gaps, divided across floor(T/4) staggered 4-row bands

So phrases buy feeder rows with tail width. This searches the trade directly.

Tail model (validated against the current 84x85 build, whose tail measures
2 + 11(decoder) + 3 + 28(year) + 2 + 11(unpack) + 2 + 11(comma) + 2 + 9(restorer)
= 81, plus the output room/pipes out to 84):

  * the year machine is 7 rows tall and eats a full-height 28-wide strip
  * every other machine is 4 rows tall, so with T tail rows the regions left
    and right of the year strip each hold floor(T/4) staggered 4-row bands
  * the 3x3 output room tucks into a 3-row leftover strip, so it is not
    charged against 4-row band capacity
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                "solutions", "history-lesson"))
import build_with_year as b

BASE = b.BASE
OFFSET = b.OFFSET
MAX_PHRASE_SYMBOLS = 9      # 92**10 overflows signed 64-bit
GAP = 3                     # columns between adjacent tail rooms (pipe)
FIXED_TAIL_ROOMS = 11 + 11 + 11 + 9   # decoder, unpack, comma, restorer
YEAR_W, YEAR_H = 28, 7


def packed_symbols(symbols, base=BASE):
    return sum(s * base**i for i, s in enumerate(symbols))


def phrase_room_width(phrase):
    packed = packed_symbols([ord(c) - OFFSET for c in phrase])
    return len(str(packed)) + 16


def tokenize(data, phrases_with_glyphs):
    """build_with_year.tokenize_with_year, generalised to N phrase glyphs."""
    symbols, i = [], 0
    expected_year = b.FIRST_GENERATED_YEAR
    encoded = [(p.encode("ascii"), g) for p, g in phrases_with_glyphs]
    while i < len(data):
        if expected_year <= b.LAST_GENERATED_YEAR:
            boundary = f"; {expected_year}: ".encode("ascii")
            if data.startswith(boundary, i):
                symbols.append(0)
                i += len(boundary)
                expected_year += 1
                continue
        for pb, glyph in encoded:
            if data.startswith(pb, i):
                symbols.append(glyph)
                i += len(pb)
                break
        else:
            ch = data[i:i + 1]
            if ch in b.PUNCT_SPACE_TOKENS and data[i:i + 2] == ch + b" ":
                symbols.append(data[i] - OFFSET)
                i += 2
                continue
            symbol = data[i] - OFFSET
            if not 1 <= symbol < BASE:
                raise ValueError(f"byte {data[i]} at {i} outside alphabet")
            symbols.append(symbol)
            i += 1
    assert expected_year == b.LAST_GENERATED_YEAR + 1
    return symbols


def best_rows(symbols, width_budget):
    """Cheapest (rows, chunks, digit_widths) with sum(digit_widths) <= budget."""
    best = None
    lo, hi = 8, 19          # >18 digits is dead weight: 92**9 is 18 digits
    for total in range(4 * lo, min(width_budget, 4 * (hi - 1)) + 1):
        for w0 in range(lo, hi):
            for w1 in range(lo, hi):
                for w2 in range(lo, hi):
                    w3 = total - w0 - w1 - w2
                    if not lo <= w3 < hi:
                        continue
                    widths = (w0, w1, w2, w3)
                    try:
                        chunks = b.pack_chunks(symbols, BASE, 10, widths)
                    except ValueError:
                        continue
                    rows = (len(chunks) + 3) // 4
                    if best is None or (rows, len(chunks)) < best[:2]:
                        best = (rows, len(chunks), widths, total)
    return best


def tail_width(num_phrases, phrase_widths, T):
    """Minimum W whose tail fits everything, given T tail rows."""
    bands = T // 4
    if bands < 1 or T < YEAR_H:
        return None
    need = FIXED_TAIL_ROOMS + sum(phrase_widths) + GAP * (4 + num_phrases)
    # bands exist both left and right of the year strip; total band capacity
    # is bands * (W - YEAR_W - margin). Solve for W.
    margin = 4
    return YEAR_W + margin + -(-need // bands)


def evaluate(data, phrases, T):
    tokens = [(p, i + 2) for i, p in enumerate(phrases)]
    if any(g > 9 for _, g in tokens):
        return None
    if any(len(p) > MAX_PHRASE_SYMBOLS for p in phrases):
        return None
    symbols = tokenize(data, tokens)
    widths = [phrase_room_width(p) for p in phrases]
    w_tail = tail_width(len(phrases), widths, T)
    if w_tail is None:
        return None
    # feeder may be wider than the tail; give it the whole budget either way
    got = best_rows(symbols, max(w_tail, 100) - 17)
    if got is None:
        return None
    rows, chunks, dw, total = got
    # the real width is whichever of feeder/tail is larger; re-solve the feeder
    # under the tail's width so we never pay for feeder columns we can't use
    best = None
    for cap in range(4 * 8, 4 * 18 + 1):
        got2 = best_rows(symbols, cap)
        if got2 is None:
            continue
        r2, c2, dw2, tot2 = got2
        W = max(tot2 + 17, w_tail)
        H = r2 + 2 + T
        box = max(W, H) ** 2
        if best is None or box < best[0]:
            best = (box, W, H, r2, c2, dw2, T, len(symbols))
    return best


if __name__ == "__main__":
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "solutions", "history-lesson")
    data = open(os.path.join(here, "icfp-history.txt"), "rb").read()

    candidates = [" and ", ", USA", " for ", "Haskell", " Canada", "Peyton ",
                  " Jones", " Simon ", " the ", "ion ", "ing "]
    text = data.decode("latin1")
    print("candidate phrases (<=9 symbols):")
    for c in candidates:
        print(f"  {c!r:12} x{text.count(c):3}  room={phrase_room_width(c)} wide")
    print()

    import itertools
    results = []
    for k in range(0, 3):
        for combo in itertools.combinations(candidates, k):
            for T in (7, 8, 11, 12):
                got = evaluate(data, list(combo), T)
                if got:
                    results.append((got, combo))
    results.sort(key=lambda r: r[0][0])
    print(f"{'box':>7} {'W':>4} {'H':>4} {'rows':>5} {'chunks':>7} {'T':>3}  "
          f"{'symbols':>7}  digit_widths / phrases")
    seen = set()
    for got, combo in results[:20]:
        box, W, H, rows, chunks, dw, T, nsym = got
        key = (box, combo)
        if key in seen:
            continue
        seen.add(key)
        print(f"{box:7} {W:4} {H:4} {rows:5} {chunks:7} {T:3}  {nsym:7}  {dw} {list(combo)}")
