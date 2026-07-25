#!/usr/bin/env python3
"""Faster rewrite of optimize_layout.py -- same model, one sweep per token set.

optimize_layout.py re-ran the digit_widths search once per width cap and once
per T, which repeats pack_chunks thousands of times. Here each token set is
tokenized once, swept over digit_widths once to get the (sum -> best rows)
frontier, and only then combined with each T.
"""
import sys, os, itertools

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                "solutions", "history-lesson"))
import build_with_year as b

BASE, OFFSET = b.BASE, b.OFFSET
MAX_PHRASE_SYMBOLS = 9
GAP = 3
FIXED_TAIL_ROOMS = 11 + 11 + 11 + 9
YEAR_W, YEAR_H = 28, 7


def packed_symbols(symbols, base=BASE):
    return sum(s * base**i for i, s in enumerate(symbols))


def phrase_room_width(phrase):
    return len(str(packed_symbols([ord(c) - OFFSET for c in phrase]))) + 16


def tokenize(data, tokens):
    symbols, i = [], 0
    expected_year = b.FIRST_GENERATED_YEAR
    encoded = [(p.encode("ascii"), g) for p, g in tokens]
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
                raise ValueError("outside alphabet")
            symbols.append(symbol)
            i += 1
    assert expected_year == b.LAST_GENERATED_YEAR + 1
    return symbols


def rows_frontier(symbols, lo=10, hi=19):
    """{sum(digit_widths): (rows, chunks, widths)} best rows for each width."""
    frontier = {}
    for w0 in range(lo, hi):
        for w1 in range(lo, hi):
            for w2 in range(lo, hi):
                for w3 in range(lo, hi):
                    widths = (w0, w1, w2, w3)
                    total = sum(widths)
                    try:
                        chunks = b.pack_chunks(symbols, BASE, 10, widths)
                    except ValueError:
                        continue
                    rows = (len(chunks) + 3) // 4
                    cur = frontier.get(total)
                    if cur is None or (rows, len(chunks)) < cur[:2]:
                        frontier[total] = (rows, len(chunks), widths)
    # a wider feeder may never do worse than a narrower one
    best = None
    for total in sorted(frontier):
        if best is not None and frontier[total][0] > best[0]:
            frontier[total] = best
        best = frontier[total]
    return frontier


def tail_width(phrase_widths, T):
    bands = T // 4
    if bands < 1 or T < YEAR_H:
        return None
    need = FIXED_TAIL_ROOMS + sum(phrase_widths) + GAP * (4 + len(phrase_widths))
    return YEAR_W + 4 + -(-need // bands)


if __name__ == "__main__":
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "solutions", "history-lesson")
    data = open(os.path.join(here, "icfp-history.txt"), "rb").read()
    text = data.decode("latin1")

    candidates = [" and ", ", USA", " for ", "Haskell", " Canada", "Peyton ",
                  " Jones", " Simon ", " the ", "ion ", "ing "]
    print("candidate phrases (<=9 symbols):")
    for c in candidates:
        print(f"  {c!r:12} x{text.count(c):3}  room={phrase_room_width(c)} wide")
    print()

    results = []
    for k in range(0, 4):
        for combo in itertools.combinations(candidates, k):
            if any(len(p) > MAX_PHRASE_SYMBOLS for p in combo):
                continue
            tokens = [(p, i + 2) for i, p in enumerate(combo)]
            symbols = tokenize(data, tokens)
            frontier = rows_frontier(symbols)
            widths = [phrase_room_width(p) for p in combo]
            for T in (7, 8, 11, 12, 15, 16):
                w_tail = tail_width(widths, T)
                if w_tail is None:
                    continue
                for total, (rows, chunks, dw) in frontier.items():
                    W = max(total + 17, w_tail)
                    H = rows + 2 + T
                    results.append((max(W, H) ** 2, W, H, rows, chunks, dw, T,
                                    len(symbols), combo))

    results.sort(key=lambda r: r[0])
    print(f"{'box':>7} {'W':>4} {'H':>4} {'rows':>5} {'chunks':>7} {'T':>3} "
          f"{'symbols':>8}  digit_widths / phrases")
    seen = set()
    shown = 0
    for box, W, H, rows, chunks, dw, T, nsym, combo in results:
        if combo in seen:
            continue
        seen.add(combo)
        print(f"{box:7} {W:4} {H:4} {rows:5} {chunks:7} {T:3} {nsym:8}  {dw} {list(combo)}")
        shown += 1
        if shown >= 15:
            break
