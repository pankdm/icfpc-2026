#!/usr/bin/env python3
"""Search the T=23 plus direct 60..65 History Lesson dictionary.

Target geometry:
  group A: positions 1..22, 3 rows
  group B: positions 23..37 plus sentinel, 3 rows x 6 slots
  source-width cap: 72 cells in a 79-column P1 room
"""
from __future__ import annotations

import itertools
import os
import sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HISTORY = os.path.join(ROOT, "solutions", "history-lesson")
sys.path[:0] = [HISTORY, os.path.join(ROOT, "tools")]

import build_ring as base
import search_feeder_dictionary as search


LOW_CODES = (2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22)
HIGH_CODES = tuple(range(60, 66))
PINNED = {
    value: base.pack128(base.spell(value))
    for value in range(1, 23)
    if value not in LOW_CODES
}
CAP = 72


def width(index, phrases):
    return len(str(base.pack128(base.phrase_bytes(phrases[index][0]))))


@lru_cache(maxsize=None)
def pair_profiles(pair_widths):
    profiles = {}
    for permutation in set(itertools.permutations(pair_widths)):
        row1 = tuple(reversed(permutation[:6]))
        row2 = permutation[6:] + (1, 1, 1)
        pair_columns = tuple(
            max(row1[column], row2[column])
            for column in range(6)
        )
        key = tuple(sorted(pair_columns))
        old = profiles.get(key)
        if old is None or permutation < old[0]:
            profiles[key] = (permutation, pair_columns)
    return tuple(profiles.values())


@lru_cache(maxsize=None)
def best_group_b_width(high_widths, pair_widths):
    """Return minimum (sum column widths, pair permutation).

    Group-B preload order at west_first=True is:
      row 0 east: positions 23..28 (the six high direct references)
      row 1 west: positions 29..34
      row 2 east: positions 35..37, two fillers, sentinel
    """
    best = None
    high_sorted = tuple(sorted(high_widths))
    for permutation, pair_columns in pair_profiles(pair_widths):
        column_order = tuple(sorted(range(6), key=lambda c: pair_columns[c]))
        high_by_column = [0] * 6
        for high_width, column in zip(high_sorted, column_order):
            high_by_column[column] = high_width
        column_widths = tuple(
            max(high_by_column[column], pair_columns[column])
            for column in range(6)
        )
        candidate = (
            sum(column_widths), permutation, column_widths,
            tuple(high_by_column),
        )
        if best is None or candidate < best:
            best = candidate
    return best


def encode_markers(stream, phrases, low_indices, high_indices, pair_indices):
    symbol_of = {}
    for index, code in zip(low_indices, LOW_CODES):
        symbol_of[index] = (code,)
    for index, code in zip(high_indices, HIGH_CODES):
        symbol_of[index] = (code,)
    for index, position in zip(pair_indices, range(29, 38)):
        symbol_of[index] = (base.ESC, position)
    symbols = []
    for marker in stream:
        if marker >= 0:
            symbols.append(marker)
        else:
            symbols.extend(symbol_of[-marker - 1])
    return symbols


def run(weight):
    old = (base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN)
    base.THRESHOLD = 23
    base.ESC = 29
    base.SMALL_FREE = list(LOW_CODES + HIGH_CODES)
    base.STOLEN = (8, 18, 23)
    try:
        stream, phrases = search.choose_weighted(
            base.tokenize(base.TEXT),
            single_slots=21,
            pair_slots=9,
            table_weight=weight,
        )
    finally:
        base.THRESHOLD, base.ESC, base.SMALL_FREE, base.STOLEN = old

    singles = tuple(i for i, (_, single) in enumerate(phrases) if single)
    pairs = tuple(i for i, (_, single) in enumerate(phrases) if not single)
    assert len(singles) == 21 and len(pairs) == 9
    pair_widths = tuple(width(i, phrases) for i in pairs)

    feasible = []
    for high_indices in itertools.combinations(singles, 6):
        high_set = frozenset(high_indices)
        low_indices = tuple(i for i in singles if i not in high_set)
        values = [base.pack128(base.phrase_bytes(phrases[i][0]))
                  for i in low_indices]
        try:
            rows, _, assignment = base.pack_group_a(
                values, PINNED, 22, True, CAP
            )
        except ValueError:
            continue
        if rows != 3:
            continue

        # pack_group_a chooses which low code receives each value. Recover
        # phrase indices in physical position order.
        by_value = {}
        for index in low_indices:
            value = base.pack128(base.phrase_bytes(phrases[index][0]))
            by_value.setdefault(value, []).append(index)
        low_by_position = []
        for code in LOW_CODES:
            value = assignment[code]
            low_by_position.append(by_value[value].pop())

        high_widths = tuple(sorted(width(i, phrases) for i in high_indices))
        group_b = best_group_b_width(high_widths, pair_widths)
        if group_b[0] + 18 > CAP:
            continue
        remaining_high = list(high_indices)
        high_order = []
        for wanted_width in group_b[3]:
            index = next(
                i for i in remaining_high
                if width(i, phrases) == wanted_width
            )
            remaining_high.remove(index)
            high_order.append(index)
        feasible.append((
            group_b[0] + 18,
            tuple(low_by_position),
            tuple(high_order),
            group_b[1],
            group_b[2],
            stream,
            phrases,
            pairs,
        ))

    print(
        f"weight={weight}: symbols-unassigned={len(stream)} "
        f"geometry-candidates={len(feasible)}"
    )
    if not feasible:
        return
    feasible.sort(key=lambda item: item[:5])
    best = feasible[0]
    _, low_order, high_order, pair_width_order, column_widths, stream, phrases, pairs = best

    # Map the width permutation back to phrase indices. Equal widths are
    # interchangeable for geometry; stable order is enough for this first
    # exact feeder measurement.
    remaining = list(pairs)
    pair_order = []
    for wanted_width in pair_width_order:
        index = next(i for i in remaining if width(i, phrases) == wanted_width)
        remaining.remove(index)
        pair_order.append(index)

    symbols = encode_markers(
        stream, phrases, low_order, high_order, tuple(pair_order)
    )
    bands = base.optimize_feeder(symbols, 79)
    print(
        f"  best groupB={best[0]} columns={column_widths} "
        f"symbols={len(symbols)} feeder={sum(b.rows for b in bands)} "
        f"chunks={sum(len(b.chunks) for b in bands)}"
    )
    print("  low:", [base.phrase_bytes(phrases[i][0]) for i in low_order])
    print("  high:", [base.phrase_bytes(phrases[i][0]) for i in high_order])
    print("  pairs:", [base.phrase_bytes(phrases[i][0]) for i in pair_order])


def main():
    for weight in (1.0, 1.25, 1.5, 2.0, 3.0):
        run(weight)


if __name__ == "__main__":
    main()
