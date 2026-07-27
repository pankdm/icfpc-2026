#!/usr/bin/env python3
"""Try symbol-count-first dictionaries under the 79-column P1 constraint."""
from __future__ import annotations

import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "solutions", "history-lesson"))

import build_ring as b  # noqa: E402


def choose_symbol(stream, single_digit_cap):
    forbidden = set(b.STOLEN) | {0, b.ESC}
    phrases = []
    for value in b.STOLEN:
        stream = b.replace_nonoverlap(
            stream, (value,), [-len(phrases) - 1],
        )
        phrases.append(((value,), False))
    singles, pairs = 15, 16
    while singles or pairs:
        n = len(stream)
        best = None
        for size in range(2, 10):
            counts = collections.Counter(
                tuple(stream[i:i + size]) for i in range(n - size + 1)
            )
            for pattern, occurrences in counts.items():
                if (
                    occurrences < 2
                    or any(s in forbidden or s < 1 for s in pattern)
                ):
                    continue
                raw = b.phrase_bytes(pattern)
                if len(raw) > 9:
                    continue
                value = b.pack128(raw)
                digits = len(str(value))
                if not b.fits_literal(value) or digits > 18:
                    continue
                hits = b.count_nonoverlap(stream, pattern)
                options = []
                if singles and digits <= single_digit_cap:
                    options.append(((size - 1) * hits, True))
                if pairs and size >= 3:
                    options.append(((size - 2) * hits, False))
                for saving, single in options:
                    key = (saving, -digits, size, hits, raw)
                    if saving > 0 and (best is None or key > best[0]):
                        best = (key, pattern, single)
        if best is None:
            break
        _, pattern, single = best
        stream = b.replace_nonoverlap(
            stream, pattern, [-len(phrases) - 1],
        )
        phrases.append((pattern, single))
        if single:
            singles -= 1
        else:
            pairs -= 1
    return stream, phrases


def main():
    b.THRESHOLD = 23
    b.ESC = 29
    b.SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    b.STOLEN = (8, 18, 23)
    original = b.choose_phrases
    for cap in (4, 5, 6, 7):
        b.choose_phrases = lambda stream, cap=cap: choose_symbol(stream, cap)
        try:
            symbols, ring, layout = b.build_encoding(
                bottom_up=True, group_a_cap=72,
            )
            span = sum(layout["TB"]) + 3 * len(layout["TB"]) + 4
            print(
                cap, len(symbols), len(ring), layout["group_a_rows"],
                layout["TB"], span, flush=True,
            )
            if (
                len(symbols) <= 2050
                and layout["group_a_rows"] <= 3
                and span <= 76
            ):
                bands = b.optimize_feeder(symbols, 79)
                print(
                    " rows", sum(band.rows for band in bands), flush=True,
                )
        except Exception as error:
            print(cap, type(error).__name__, error, flush=True)
    b.choose_phrases = original


if __name__ == "__main__":
    main()
