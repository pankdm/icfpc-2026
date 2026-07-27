#!/usr/bin/env python3
"""Search spare six-row dictionary cells across feeder radices."""
from __future__ import annotations

import multiprocessing
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [
    os.path.join(ROOT, "solutions", "history-lesson"),
    os.path.join(ROOT, "tools"),
    os.path.join(ROOT, "scratchpad", "history-high-run"),
]

import assign_search
import build_ring as base

RING_ENTRIES = 38


def encoding(weight):
    old = (base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN)
    base.THRESHOLD = 23
    base.ESC = 29
    base.SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    base.STOLEN = (8, 18, 23)
    selector = lambda stream: base.choose_phrases_weighted(
        stream, ring_entries=RING_ENTRIES, table_weight=weight
    )
    try:
        symbols, ring, layout = base.build_encoding(
            west_first=True,
            phrase_selector=selector,
            group_b_rows=3,
            group_a_cap=72,
        )
    finally:
        base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN = old
    if layout["group_a_rows"] != 3 or len(ring) != RING_ENTRIES:
        return None
    return weight, symbols, layout["TB"]


def exact(job):
    weight, symbols, radix = job
    bands = base.optimize_feeder(symbols, 79, base=radix)
    return (
        sum(band.rows for band in bands),
        sum(len(band.chunks) for band in bands),
        len(symbols),
        weight,
        radix,
    )


def main():
    candidates = []
    for weight in (0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
        result = encoding(weight)
        if result is None:
            continue
        if sum(result[2]) + 18 > 72:
            continue
        proxy = assign_search.proxy(result[1])
        candidates.append((proxy, *result))
        print("candidate", weight, len(result[1]), proxy, result[2], flush=True)
    unique = {}
    for proxy, weight, symbols, widths in sorted(candidates):
        unique.setdefault(tuple(symbols), (proxy, weight, symbols, widths))
    streams = sorted(unique.values())[:1]
    jobs = [
        (weight, symbols, radix)
        for _, weight, symbols, _ in streams
        for radix in range(92, 100)
    ]
    with multiprocessing.Pool(4) as workers:
        results = list(workers.imap_unordered(exact, jobs))
    results.sort()
    for result in results:
        print("exact", result, flush=True)
    return 0 if results[0][0] <= 62 else 1


if __name__ == "__main__":
    raise SystemExit(main())
