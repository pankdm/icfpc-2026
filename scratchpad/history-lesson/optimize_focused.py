#!/usr/bin/env python3
"""Focused version of the optimize_layout sweep -- small candidate set, coarse
width grid, so it finishes in seconds instead of hours.

Same model as optimize_layout2.py (see its docstring for the tail geometry).
The exhaustive version was O(232 combos x 6561 width tuples x pack_chunks over
2500 symbols); here the phrase candidates are pre-ranked by savings and the
digit-width grid is narrowed to the range that actually matters (a slot wider
than 18 digits is dead weight, since 92**9 is already 18 digits).
"""
import sys, os, itertools

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                "solutions", "history-lesson"))
import build_with_year as b

BASE, OFFSET = b.BASE, b.OFFSET
GAP = 3
FIXED_TAIL_ROOMS = 11 + 11 + 11 + 9     # decoder, unpack, comma, restorer
YEAR_W, YEAR_H = 28, 7


def packed(phrase):
    return sum((ord(c) - OFFSET) * BASE**i for i, c in enumerate(phrase))


def phrase_room_width(phrase):
    return len(str(packed(phrase))) + 16


def tokenize(data, tokens):
    symbols, i = [], 0
    year = b.FIRST_GENERATED_YEAR
    enc = [(p.encode("ascii"), g) for p, g in tokens]
    while i < len(data):
        if year <= b.LAST_GENERATED_YEAR:
            boundary = f"; {year}: ".encode("ascii")
            if data.startswith(boundary, i):
                symbols.append(0); i += len(boundary); year += 1; continue
        for pb, g in enc:
            if data.startswith(pb, i):
                symbols.append(g); i += len(pb); break
        else:
            ch = data[i:i + 1]
            if ch in b.PUNCT_SPACE_TOKENS and data[i:i + 2] == ch + b" ":
                symbols.append(data[i] - OFFSET); i += 2; continue
            s = data[i] - OFFSET
            assert 1 <= s < BASE
            symbols.append(s); i += 1
    assert year == b.LAST_GENERATED_YEAR + 1
    return symbols


def rows_frontier(symbols, lo=13, hi=19):
    """{sum(widths): (rows, chunks, widths)}, monotone-improved."""
    frontier = {}
    for widths in itertools.product(range(lo, hi), repeat=4):
        total = sum(widths)
        cur = frontier.get(total)
        if cur is not None and cur[0] <= (len(symbols) // 40):
            pass
        try:
            chunks = b.pack_chunks(symbols, BASE, 10, widths)
        except ValueError:
            continue
        rows = (len(chunks) + 3) // 4
        if cur is None or (rows, len(chunks)) < cur[:2]:
            frontier[total] = (rows, len(chunks), widths)
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

    candidates = [" and ", ", USA", " for ", "Haskell", " Canada"]
    print("candidates:")
    for c in candidates:
        n = text.count(c)
        print(f"  {c!r:12} x{n:3}  saves~{(len(c)-1)*n:4} symbols  room={phrase_room_width(c)} wide")
    print()

    rows_out = []
    for k in range(0, len(candidates) + 1):
        for combo in itertools.combinations(candidates, k):
            tokens = [(p, i + 2) for i, p in enumerate(combo)]
            symbols = tokenize(data, tokens)
            frontier = rows_frontier(symbols)
            widths = [phrase_room_width(p) for p in combo]
            best = None
            for T in (7, 8, 11, 12, 15, 16):
                wt = tail_width(widths, T)
                if wt is None:
                    continue
                for total, (rows, chunks, dw) in frontier.items():
                    W = max(total + 17, wt)
                    H = rows + 2 + T
                    box = max(W, H) ** 2
                    if best is None or box < best[0]:
                        best = (box, W, H, rows, chunks, dw, T, len(symbols), wt)
            rows_out.append((best, combo))

    rows_out.sort(key=lambda r: r[0][0])
    print(f"{'box':>7} {'W':>4} {'H':>4} {'rows':>5} {'chunk':>6} {'T':>3} "
          f"{'Wtail':>6} {'syms':>6}  widths / phrases")
    for best, combo in rows_out:
        box, W, H, rows, chunks, dw, T, nsym, wt = best
        print(f"{box:7} {W:4} {H:4} {rows:5} {chunks:6} {T:3} {wt:6} {nsym:6}  "
              f"{dw} {list(combo)}")
