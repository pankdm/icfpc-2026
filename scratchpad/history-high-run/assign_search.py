#!/usr/bin/env python3
"""Randomized code-assignment search for the feasible high-run dictionary."""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HISTORY = os.path.join(ROOT, "solutions", "history-lesson")
sys.path[:0] = [HISTORY, os.path.join(ROOT, "tools")]

import build_ring as base
import search_feeder_dictionary as search

LOW_CODES = (2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22)
HIGH_CODES = tuple(range(60, 66))
CAP = 72

LOW_WORDS = (
    b"an", b"er", b", USA", b"Sim", b"al", b"es", b'" (', b" Peyt",
    b"en", b"ti", b"or", b"st", b"in", b"and ", b"on",
)
HIGH_WORDS = (b"Haskell", b"ar", b"el", b"e ", b"t ", b' "')
PAIR_WORDS = (
    b"'", b"1", b"6", b"ed ", b"burg", b"trios Vy",
    b" program", b"David ", b" of ",
)


def packed(index, phrases):
    return base.pack128(base.phrase_bytes(phrases[index][0]))


def digits(index, phrases):
    return len(str(packed(index, phrases)))


def word_indices(phrases, words):
    by_word = {base.phrase_bytes(phrase): i
               for i, (phrase, _) in enumerate(phrases)}
    return tuple(by_word[word] for word in words)


def group_a_ok(low, phrases):
    ring = {}
    for code in range(1, 23):
        if code not in LOW_CODES:
            ring[code] = base.pack128(base.spell(code))
    for code, index in zip(LOW_CODES, low):
        ring[code] = packed(index, phrases)
    try:
        _, widths, rows, slots = base.group_a_grid(
            [ring[code] for code in range(1, 23)], True, CAP
        )
    except ValueError:
        return None
    if rows != 3:
        return None
    return widths, slots


def group_b_ok(high, pairs, phrases):
    high_widths = tuple(digits(index, phrases) for index in high)
    row1 = tuple(reversed(tuple(digits(index, phrases)
                                for index in pairs[:6])))
    row2 = tuple(digits(index, phrases) for index in pairs[6:]) + (1, 1, 1)
    columns = tuple(
        max(high_widths[column], row1[column], row2[column])
        for column in range(6)
    )
    return columns if sum(columns) + 18 <= CAP else None


def encode(markers, phrases, low, high, pairs):
    symbol_of = {}
    for index, code in zip(low, LOW_CODES):
        symbol_of[index] = (code,)
    for index, code in zip(high, HIGH_CODES):
        symbol_of[index] = (code,)
    for index, position in zip(pairs, range(29, 38)):
        symbol_of[index] = (base.ESC, position)
    symbols = []
    for marker in markers:
        if marker >= 0:
            symbols.append(marker)
        else:
            symbols.extend(symbol_of[-marker - 1])
    return symbols


def greedy_chunks(symbols):
    result = []
    index = 0
    while index < len(symbols):
        for count in range(min(9, len(symbols) - index), 0, -1):
            if symbols[index + count - 1] == 0:
                continue
            value = sum(
                symbols[index + offset] * base.B1 ** offset
                for offset in range(count)
            )
            if base.fits_literal(value):
                result.append(len(str(value)))
                index += count
                break
        else:
            raise AssertionError(index)
    return result


def proxy(symbols):
    widths = greedy_chunks(symbols)
    rows = 0
    index = 0
    while index < len(widths):
        remaining = len(widths) - index
        best = 0
        for slots in range(1, min(10, remaining // 2) + 1):
            cost = 5 + 3 * slots + sum(
                max(widths[index + j], widths[index + 2 * slots - 1 - j])
                for j in range(slots)
            )
            if cost <= 79:
                best = slots
        if best:
            index += 2 * best
            rows += 2
        else:
            # The exact optimizer handles the final partial band. This proxy
            # only needs a stable ordering for candidate selection.
            index += min(5, remaining)
            rows += 1
    return rows, len(widths), sum(widths)


def exact_worker(item):
    key, symbols, state = item
    sys.path[:0] = [HISTORY, os.path.join(ROOT, "tools")]
    import build_ring
    bands = build_ring.optimize_feeder(symbols, 79)
    return (
        sum(band.rows for band in bands),
        sum(len(band.chunks) for band in bands),
        key,
        state,
    )


def main():
    old = (base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN)
    base.THRESHOLD = 23
    base.ESC = 29
    base.SMALL_FREE = list(LOW_CODES + HIGH_CODES)
    base.STOLEN = (8, 18, 23)
    try:
        markers, phrases = search.choose_weighted(
            base.tokenize(base.TEXT),
            single_slots=21,
            pair_slots=9,
            table_weight=1.25,
        )
    finally:
        base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN = old

    low = list(word_indices(phrases, LOW_WORDS))
    high = list(word_indices(phrases, HIGH_WORDS))
    pairs = list(word_indices(phrases, PAIR_WORDS))
    assert group_a_ok(low, phrases) and group_b_ok(high, pairs, phrases)

    rng = random.Random(790079)
    best = {}
    current = (low, high, pairs)
    for iteration in range(100_000):
        low, high, pairs = (list(part) for part in current)
        move = rng.randrange(4)
        if move == 0:
            # Explore different choices for the promoted high run.
            a, b = rng.randrange(15), rng.randrange(6)
            low[a], high[b] = high[b], low[a]
        elif move == 1:
            rng.shuffle(high)
        elif move == 2:
            rng.shuffle(pairs)
        else:
            rng.shuffle(low)
        if not group_a_ok(low, phrases) or not group_b_ok(high, pairs, phrases):
            continue
        current = (low, high, pairs)
        symbols = encode(markers, phrases, low, high, pairs)
        key = proxy(symbols)
        state_key = (tuple(low), tuple(high), tuple(pairs))
        if state_key not in best:
            best[state_key] = (key, symbols)
        if iteration and iteration % 10_000 == 0:
            print(
                f"sampled={iteration} feasible={len(best)} "
                f"proxy={min(value[0] for value in best.values())}",
                flush=True,
            )

    ranked = sorted(
        (key, symbols, state)
        for state, (key, symbols) in best.items()
    )[:24]
    print(f"exact finalists={len(ranked)} best-proxy={ranked[0][0]}")
    # ProcessPoolExecutor probes SC_SEM_NSEMS_MAX on macOS, which is denied in
    # the contest workspace sandbox. There are only a few dozen finalists, so
    # exact-grade them directly.
    results = [exact_worker(item) for item in ranked]
    results.sort()
    for result in results[:8]:
        print("exact", result[:3])
    winner = results[0]
    rows, chunks, key, state = winner
    output = {
        "rows": rows,
        "chunks": chunks,
        "proxy": key,
        "low": [base.phrase_bytes(phrases[i][0]).decode("ascii")
                for i in state[0]],
        "high": [base.phrase_bytes(phrases[i][0]).decode("ascii")
                 for i in state[1]],
        "pairs": [base.phrase_bytes(phrases[i][0]).decode("ascii")
                  for i in state[2]],
    }
    path = os.path.join(HERE, "assignment.json")
    with open(path, "w") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
