#!/usr/bin/env python3
"""Search width-feasible 36-word Route-B streams across nearby radices."""
from __future__ import annotations

import multiprocessing
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [
    os.path.join(ROOT, "solutions", "history-lesson"),
]

import build_ring as b  # noqa: E402


def candidates():
    low = list(b.SMALL_FREE)
    b.SMALL_FREE = low + list(range(60, 66))
    base_stream, base_phrases = b.choose_phrases(b.tokenize(b.TEXT))
    b.SMALL_FREE = low
    result = []
    for drop, (pattern, single) in enumerate(base_phrases):
        if single is not False or (
            len(pattern) == 1 and pattern[0] in b.STOLEN
        ):
            continue
        stream = b.replace_nonoverlap(
            list(base_stream), (-drop - 1,), list(pattern),
        )
        phrases = list(base_phrases)
        phrases[drop] = (pattern, None)
        singles = [i for i, (_, kind) in enumerate(phrases) if kind is True]
        pairs = [i for i, (_, kind) in enumerate(phrases) if kind is False]
        value = lambda i: b.pack128(b.phrase_bytes(phrases[i][0]))
        ring, symbol_of = {}, {}
        for i, position in zip(singles[:len(low)], low):
            ring[position] = value(i)
            symbol_of[i] = [position]
        for raw in range(1, 17):
            ring.setdefault(raw, b.pack128(b.spell(raw)))
        high = singles[len(low):]
        for offset, i in enumerate(high):
            ring[17 + offset] = value(i)
            symbol_of[i] = [60 + offset]
        position = 17 + len(high)
        for i in pairs:
            ring[position] = value(i)
            symbol_of[i] = [b.ESC, position]
            position += 1
        symbols = []
        for token in stream:
            symbols.extend(
                [token] if token >= 0 else symbol_of[-token - 1]
            )
        widths = sorted(
            [len(str(value(i))) for i in high + pairs] + [1],
            reverse=True,
        )
        profile = widths[::4]
        if sum(profile) + 3 * len(profile) <= 72:
            result.append((b.phrase_bytes(pattern), symbols))
    return result


def evaluate(job):
    name, symbols, radix = job
    bands = b.optimize_feeder(symbols, 79, base=radix)
    return (
        sum(band.rows for band in bands),
        sum(len(band.chunks) for band in bands),
        radix,
        name,
    )


def main():
    jobs = [
        (name, symbols, radix)
        for name, symbols in candidates()
        for radix in (92, 93, 94)
    ]
    with multiprocessing.Pool(4) as pool:
        for rows, chunks, radix, name in pool.imap_unordered(evaluate, jobs):
            print(rows, chunks, radix, repr(name), flush=True)
            if rows <= 61:
                pool.terminate()
                return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
