#!/usr/bin/env python3
"""Joint direct/escaped assignment search for the 39-entry dictionary."""
from __future__ import annotations

import json
import multiprocessing
import os
import random
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


def configure():
    base.THRESHOLD = 23
    base.ESC = 29
    base.SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    base.STOLEN = (8, 18, 23)


def initial():
    configure()
    return base.choose_phrases_weighted(
        base.tokenize(base.TEXT), ring_entries=39, table_weight=1.0
    )


def evaluate(markers, phrases):
    configure()
    selector = lambda stream: (list(markers), list(phrases))
    try:
        symbols, ring, layout = base.build_encoding(
            west_first=True,
            phrase_selector=selector,
            group_b_rows=3,
            group_a_cap=72,
        )
    except (AssertionError, ValueError):
        return None
    span = sum(layout["TB"]) + 3 * len(layout["TB"])
    if layout["group_a_rows"] != 3 or len(ring) != 39:
        return None
    return (
        span, assign_search.proxy(symbols), len(symbols),
        symbols, phrases, layout,
    )


def exact(item):
    key, symbols, phrases, layout = item
    bands = base.optimize_feeder(symbols, 79)
    return (
        sum(band.rows for band in bands),
        sum(len(band.chunks) for band in bands),
        key,
        symbols,
        phrases,
        layout,
    )


def main():
    markers, start = initial()
    forced = {tuple([value]) for value in base.STOLEN}
    randomizer = random.Random(7939)
    current = list(start)
    current_result = evaluate(markers, current)
    assert current_result is not None
    feasible = {}
    for iteration in range(80_000):
        trial = list(current)
        singles = [i for i, (_, direct) in enumerate(trial) if direct is True]
        pairs = [
            i for i, (phrase, direct) in enumerate(trial)
            if direct is False and phrase not in forced
        ]
        left = randomizer.choice(singles)
        right = randomizer.choice(pairs)
        trial[left] = (trial[left][0], False)
        trial[right] = (trial[right][0], True)
        result = evaluate(markers, trial)
        if result is None:
            continue
        span, proxy, count, symbols, phrases, layout = result
        old_span, old_proxy, old_count, *_ = current_result
        old_key = (max(0, old_span - 72), old_count, old_proxy)
        new_key = (max(0, span - 72), count, proxy)
        if new_key <= old_key or randomizer.random() < 0.015:
            current = trial
            current_result = result
        if span <= 72:
            feasible.setdefault(
                tuple((phrase, direct) for phrase, direct in phrases),
                ((proxy, count), symbols, phrases, layout),
            )
        if iteration % 5000 == 0 and feasible:
            print(
                "sampled", iteration, "feasible", len(feasible),
                "best", min(value[0] for value in feasible.values()),
                flush=True,
            )

    ranked = sorted(feasible.values(), key=lambda item: item[0])[:24]
    print("exact finalists", len(ranked), flush=True)
    with multiprocessing.Pool(4) as workers:
        results = list(workers.imap_unordered(exact, ranked))
    results.sort()
    for result in results[:12]:
        print("exact", result[:3], flush=True)
    winner = results[0]
    output = {
        "rows": winner[0],
        "chunks": winner[1],
        "proxy": winner[2],
        "symbols": len(winner[3]),
        "phrases": [
            {
                "phrase": base.phrase_bytes(phrase).decode("ascii"),
                "direct": direct,
            }
            for phrase, direct in winner[4]
        ],
    }
    with open(os.path.join(HERE, "ring39_assignment.json"), "w") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    print(json.dumps(output, indent=2))
    return 0 if winner[0] <= 62 else 1


if __name__ == "__main__":
    raise SystemExit(main())
