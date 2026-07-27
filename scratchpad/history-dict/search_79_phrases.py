#!/usr/bin/env python3
"""Search equal-size dictionary swaps for a 61-row width-79 feeder.

Drop the weakest existing pair phrase (``" of "``) and replace it with five
of the six equal-saving short candidates.  This keeps the group-B entry count,
P1 dimensions, and stream symbol count unchanged while perturbing packed-i64
boundaries.
"""
from __future__ import annotations

import itertools
import multiprocessing
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [
    os.path.join(ROOT, "solutions", "history-lesson"),
    os.path.join(ROOT, "tools"),
]

import build_ring as base  # noqa: E402

CANDIDATES = (
    b"John ",
    b" high",
    b"Matth",
    b"modul",
    b"s Vyt",
    b"ystem",
    b", Swed",
    b", BC, C",
)


def configure():
    base.THRESHOLD = 23
    base.ESC = 29
    base.SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    base.STOLEN = (8, 18, 23)


def tokens_for_bytes(data: bytes) -> tuple[int, ...]:
    return tuple(byte - 31 for byte in data)


def evaluate(chosen: tuple[bytes, ...]):
    configure()
    original_choose = base.choose_phrases
    original_add = base.add_best_pair_phrases

    def choose_without_of(stream):
        stream, phrases = original_choose(stream)
        for i, (pattern, single) in enumerate(phrases):
            if base.phrase_bytes(pattern) == b" of ":
                assert single is False
                stream = base.replace_nonoverlap(
                    stream, (-i - 1,), list(pattern),
                )
                phrases[i] = (pattern, None)
                break
        else:
            raise AssertionError('missing " of " phrase')
        return stream, phrases

    patterns = tuple(tokens_for_bytes(data) for data in chosen)

    def add_selected(stream, phrases, count):
        assert count == len(patterns)
        for pattern in patterns:
            stream = base.replace_nonoverlap(
                stream, pattern, [-len(phrases) - 1],
            )
            phrases.append((pattern, False))
        return stream, list(chosen)

    base.choose_phrases = choose_without_of
    base.add_best_pair_phrases = add_selected
    try:
        symbols, ring, layout = base.build_encoding(
            extra_pair_count=5,
            bottom_up=True,
            group_a_cap=72,
        )
    finally:
        base.choose_phrases = original_choose
        base.add_best_pair_phrases = original_add
    bands = base.optimize_feeder(symbols, 79)
    rows = sum(band.rows for band in bands)
    return (
        rows, len(symbols), chosen, len(ring), layout["TB"],
        max(band.required_width for band in bands),
    )


def main():
    best = 1000
    jobs = list(itertools.combinations(CANDIDATES, 5))
    with multiprocessing.Pool(4) as pool:
        for result in pool.imap_unordered(evaluate, jobs):
            rows, symbols, chosen, ring, widths, max_width = result
            print(
                rows, symbols,
                ",".join(item.decode() for item in chosen),
                f"ring={ring}", f"TB={widths}", f"maxW={max_width}",
                flush=True,
            )
            best = min(best, rows)
    return 0 if best <= 61 else 1


if __name__ == "__main__":
    raise SystemExit(main())
