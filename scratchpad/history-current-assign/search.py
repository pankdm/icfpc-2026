#!/usr/bin/env python3
"""Search base-92 code assignments for the existing T=23 dictionary.

The phrase set, 37-entry ring, six-row dictionary, and dispatcher semantics
stay fixed. Only phrase-to-code assignments change, which changes feeder
literal values and therefore the exact 79-column packing.
"""
from __future__ import annotations

import concurrent.futures
import itertools
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HISTORY = os.path.join(ROOT, "solutions", "history-lesson")
sys.path[:0] = [HISTORY, os.path.join(ROOT, "tools")]

import build_ring as base
import search_feeder_dictionary as search

LOW_CODES = (2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22)
PINNED = {
    value: base.pack128(base.spell(value))
    for value in range(1, 23)
    if value not in LOW_CODES
}
CAP = 72


def selected():
    old = (base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN)
    base.THRESHOLD = 23
    base.ESC = 29
    base.SMALL_FREE = list(LOW_CODES)
    base.STOLEN = (8, 18, 23)
    try:
        markers, phrases = search.choose_weighted(
            base.tokenize(base.TEXT),
            single_slots=15,
            pair_slots=15,
            table_weight=1.24,
        )
    finally:
        base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN = old
    return markers, phrases


def baseline_assignment(phrases):
    def selector(stream):
        return search.choose_weighted(
            stream,
            single_slots=15,
            pair_slots=15,
            table_weight=1.24,
        )

    old = (base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN)
    base.THRESHOLD = 23
    base.ESC = 29
    base.SMALL_FREE = list(LOW_CODES)
    base.STOLEN = (8, 18, 23)
    try:
        _, ring, _ = base.build_encoding(
            threshold=23,
            west_first=True,
            group_b_rows=3,
            group_a_cap=72,
            phrase_selector=selector,
        )
    finally:
        base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN = old

    by_value = {}
    for index, (_, single) in enumerate(phrases):
        by_value.setdefault(packed(index, phrases), []).append(index)

    def take(value, single):
        matches = by_value[value]
        for offset, index in enumerate(matches):
            if bool(phrases[index][1]) == single:
                return matches.pop(offset)
        raise AssertionError((value, single))

    low = [take(ring[code], True) for code in LOW_CODES]
    pairs = [take(ring[position], False) for position in range(23, 38)]
    return low, pairs


def packed(index, phrases):
    return base.pack128(base.phrase_bytes(phrases[index][0]))


def group_a_ok(low, phrases):
    values = {code: PINNED.get(code, packed(index, phrases))
              for code, index in zip(LOW_CODES, low)}
    values.update(PINNED)
    grid, widths, rows, slots = base.group_a_grid(
        [values[position] for position in range(1, 23)], True, CAP
    )
    return rows == 3


def group_b_widths(pairs, phrases):
    widths = [len(str(packed(index, phrases))) for index in pairs]
    walk = tuple(
        (row, column)
        for row, columns in enumerate((range(6), range(5, -1, -1), range(6)))
        for column in columns
    )
    # The last walk cell is the sentinel. Choose the two other unsent filler
    # cells, then place positions 23..37 in the remaining traversal cells.
    best = None
    for holes in itertools.combinations(range(17), 2):
        grid = [[1] * 6 for _ in range(3)]
        source = iter(widths)
        for offset, (row, column) in enumerate(walk):
            if offset in holes or offset == 17:
                continue
            grid[row][column] = next(source)
        columns = tuple(
            max(grid[row][column] for row in range(3))
            for column in range(6)
        )
        candidate = (sum(columns), columns, holes)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    # p1_room's west-first turn and pump need four cells beyond the slots.
    return best if best[0] + 18 + 4 <= CAP + 4 else None


def encode(markers, low, pairs):
    symbol_of = {}
    for index, code in zip(low, LOW_CODES):
        symbol_of[index] = (code,)
    for index, position in zip(pairs, range(23, 38)):
        symbol_of[index] = (base.ESC, position)
    symbols = []
    for marker in markers:
        if marker >= 0:
            symbols.append(marker)
        else:
            symbols.extend(symbol_of[-marker - 1])
    return symbols


def greedy_widths(symbols):
    widths = []
    index = 0
    while index < len(symbols):
        for count in range(min(9, len(symbols) - index), 0, -1):
            if symbols[index + count - 1] == 0:
                continue
            value = sum(
                symbols[index + offset] * base.B1**offset
                for offset in range(count)
            )
            spelling = str(value)
            if value < 2**63 and int(spelling[::-1]) < 2**63:
                widths.append(len(spelling))
                index += count
                break
        else:
            raise AssertionError(index)
    return widths


def fixed_rows(widths):
    """Minimum rows when greedy chunk boundaries are held fixed."""
    n = len(widths)
    infinity = n + 1
    cost = [infinity] * (n + 1)
    cost[0] = 0
    for start in range(n):
        if cost[start] == infinity:
            continue
        for slots in range(1, 7):
            end = start + 2 * slots
            if end > n:
                break
            digits = sum(
                max(widths[start + j], widths[end - 1 - j])
                for j in range(slots)
            )
            if 5 + 3 * slots + digits <= 79:
                cost[end] = min(cost[end], cost[start] + 2)
        # A final single row does not need vertical literal pairing.
        remaining = n - start
        if 1 <= remaining <= 6 and 5 + 3 * remaining + sum(widths[start:]) <= 79:
            cost[n] = min(cost[n], cost[start] + 1)
    return cost[n]


def proxy(symbols):
    widths = greedy_widths(symbols)
    return fixed_rows(widths), len(widths), sum(widths)


def words(indices, phrases):
    return [base.phrase_bytes(phrases[index][0]).decode("ascii")
            for index in indices]


def indices(names, phrases):
    lookup = {
        base.phrase_bytes(phrase).decode("ascii"): index
        for index, (phrase, _) in enumerate(phrases)
    }
    return [lookup[name] for name in names]


def exact(state):
    markers, phrases = selected()
    low = indices(state["low"], phrases)
    pairs = indices(state["pairs"], phrases)
    symbols = encode(markers, low, pairs)
    bands = base.optimize_feeder(symbols, 79, max_slots=6)
    return {
        **state,
        "rows": sum(band.rows for band in bands),
        "chunks": sum(len(band.chunks) for band in bands),
        "max_used": max(band.required_width for band in bands),
    }


def worker(index):
    with open(os.path.join(HERE, "finalists.json")) as handle:
        state = json.load(handle)[index]
    print(json.dumps(exact(state)))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(int(sys.argv[2]))
        return

    markers, phrases = selected()
    low, pairs = baseline_assignment(phrases)
    assert len(low) == len(LOW_CODES) and len(pairs) == 15

    rng = random.Random(797923)
    ranked = {}
    current_low, current_pairs = list(low), list(pairs)
    for iteration in range(120_000):
        trial_low = list(current_low)
        trial_pairs = list(current_pairs)
        if rng.randrange(2):
            left, right = rng.sample(range(len(trial_low)), 2)
            trial_low[left], trial_low[right] = (
                trial_low[right], trial_low[left]
            )
        else:
            left, right = rng.sample(range(len(trial_pairs)), 2)
            trial_pairs[left], trial_pairs[right] = (
                trial_pairs[right], trial_pairs[left]
            )
        if not group_a_ok(trial_low, phrases):
            continue
        columns = group_b_widths(trial_pairs, phrases)
        if columns is None:
            continue
        current_low, current_pairs = trial_low, trial_pairs
        symbols = encode(markers, trial_low, trial_pairs)
        key = (*proxy(symbols), *columns)
        state = {
            "proxy": list(key),
            "low": words(trial_low, phrases),
            "pairs": words(trial_pairs, phrases),
        }
        identity = (tuple(trial_low), tuple(trial_pairs))
        ranked[identity] = (key, state)
        if iteration and iteration % 20_000 == 0:
            print(
                f"sampled={iteration} feasible={len(ranked)} "
                f"best={min(value[0] for value in ranked.values())}",
                flush=True,
            )

    finalists = [
        state
        for _, state in sorted(ranked.values(), key=lambda item: item[0])[:32]
    ]
    os.makedirs(HERE, exist_ok=True)
    with open(os.path.join(HERE, "finalists.json"), "w") as handle:
        json.dump(finalists, handle)

    script = os.path.abspath(__file__)

    def launch(index):
        result = subprocess.run(
            [sys.executable, script, "--worker", str(index)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(launch, range(len(finalists))))
    results.sort(key=lambda item: (
        item["rows"], item["chunks"], item["proxy"], item["low"], item["pairs"]
    ))
    for result in results[:8]:
        print("exact", result["rows"], result["chunks"], result["proxy"])
    winner = results[0]
    with open(os.path.join(HERE, "assignment.json"), "w") as handle:
        json.dump(winner, handle, indent=2)
        handle.write("\n")
    print(json.dumps(winner, indent=2))


if __name__ == "__main__":
    main()
