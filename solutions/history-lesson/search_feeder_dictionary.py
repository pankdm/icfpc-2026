#!/usr/bin/env python3
"""Quick feeder/dictionary search for the 79x79 History Lesson line.

The search keeps the 80x80 build's dictionary budget: 37 ring entries in
seven preload rows.  It compares the checked-in 81x81 and 80x80 encodings,
then tries fixed-capacity phrase dictionaries which optimize stream symbols
instead of the older source-cell heuristic.  Only the shortest feasible
streams pay for the comparatively expensive exact feeder DP.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "tools")]

import build_ring as ring


CONFIG_81 = {
    "name": "81x81",
    "threshold": 17,
    "esc": 29,
    "small_free": [2, 4, 5, 6, 7, 8, 11, 12, 16],
    "stolen": [8, 17],
}
CONFIG_80 = {
    "name": "80x80",
    "threshold": 23,
    "esc": 29,
    "small_free": [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22],
    "stolen": [8, 18, 23],
}
_SELECTION_CACHE = {}


@contextlib.contextmanager
def alphabet(config):
    old = (ring.THRESHOLD, ring.ESC, ring.SMALL_FREE, ring.STOLEN)
    ring.THRESHOLD = config["threshold"]
    ring.ESC = config["esc"]
    ring.SMALL_FREE = list(config["small_free"])
    ring.STOLEN = tuple(config["stolen"])
    try:
        yield
    finally:
        ring.THRESHOLD, ring.ESC, ring.SMALL_FREE, ring.STOLEN = old


def candidates(stream):
    """Return valid recurring phrases and their current non-overlap counts."""
    forbidden = set(ring.STOLEN) | {0, ring.ESC}
    found = {}
    for size in range(2, 10):
        counts = Counter(
            tuple(stream[i:i + size])
            for i in range(len(stream) - size + 1)
            if all(v >= 1 and v not in forbidden
                   for v in stream[i:i + size])
        )
        for phrase, count in counts.items():
            if count < 2 or len(ring.phrase_bytes(phrase)) > 9:
                continue
            value = ring.pack128(ring.phrase_bytes(phrase))
            if not ring.fits_literal(value) or len(str(value)) > 18:
                continue
            hits = ring.count_nonoverlap(stream, phrase)
            if hits >= 2:
                found[phrase] = hits
    return found


def choose_fixed(stream, single_slots, pair_slots, order):
    """Greedily fill an exact dictionary capacity under several orderings."""
    phrases = []
    for value in ring.STOLEN:
        stream = ring.replace_nonoverlap(
            stream, (value,), [-len(phrases) - 1]
        )
        phrases.append(((value,), False))
        pair_slots -= 1
    if pair_slots < 0:
        raise ValueError("forced stolen entries exceed the pair budget")

    remaining = {"single": single_slots, "pair": pair_slots}
    if order == "direct-first":
        phases = ("single", "pair")
    elif order == "pair-first":
        phases = ("pair", "single")
    else:
        phases = ("mixed",)

    for phase in phases:
        while (
            any(remaining.values()) if phase == "mixed"
            else remaining[phase] > 0
        ):
            best = None
            for phrase, hits in candidates(stream).items():
                kinds = (
                    [phase] if phase != "mixed"
                    else [kind for kind, slots in remaining.items() if slots]
                )
                for kind in kinds:
                    saving = (len(phrase) - (1 if kind == "single" else 2)) * hits
                    if saving <= 0:
                        continue
                    value = ring.pack128(ring.phrase_bytes(phrase))
                    # Stable ties prefer smaller preload literals and phrases
                    # with more occurrences (they tend to repair chunk edges).
                    key = (
                        saving,
                        hits,
                        -len(str(value)),
                        len(phrase),
                        ring.phrase_bytes(phrase),
                        kind,
                    )
                    if best is None or key > best[0]:
                        best = (key, phrase, kind)
            if best is None:
                break
            _, phrase, kind = best
            stream = ring.replace_nonoverlap(
                stream, phrase, [-len(phrases) - 1]
            )
            phrases.append((phrase, kind == "single"))
            remaining[kind] -= 1
    if any(remaining.values()):
        raise ValueError(f"could not fill dictionary slots: {remaining}")
    return stream, phrases


def choose_weighted(stream, single_slots, pair_slots, table_weight):
    """Fill the fixed table using the original source-cost score at new weights.

    ``table_weight=1`` is the checked-in selector's objective.  Nearby weights
    expose the symbol-count/table-width frontier without changing either the
    ring-entry count or the dictionary row budget.
    """
    phrases = []
    for value in ring.STOLEN:
        stream = ring.replace_nonoverlap(
            stream, (value,), [-len(phrases) - 1]
        )
        phrases.append(((value,), False))
        pair_slots -= 1
    remaining = {"single": single_slots, "pair": pair_slots}
    while any(remaining.values()):
        best = None
        for phrase, hits in candidates(stream).items():
            value = ring.pack128(ring.phrase_bytes(phrase))
            table_cells = len(str(value)) + 3
            for kind, slots in remaining.items():
                if not slots:
                    continue
                saving = (len(phrase) - (1 if kind == "single" else 2)) * hits
                if saving <= 0:
                    continue
                score = math.log10(ring.B1) * saving - table_weight * table_cells
                key = (
                    score,
                    saving,
                    hits,
                    -table_cells,
                    ring.phrase_bytes(phrase),
                    kind,
                )
                if best is None or key > best[0]:
                    best = (key, phrase, kind)
        if best is None:
            raise ValueError(f"could not fill dictionary slots: {remaining}")
        _, phrase, kind = best
        stream = ring.replace_nonoverlap(
            stream, phrase, [-len(phrases) - 1]
        )
        phrases.append((phrase, kind == "single"))
        remaining[kind] -= 1
    return stream, phrases


def optimal_segment(stream, phrases):
    by_first = {}
    for index, (phrase, single) in enumerate(phrases):
        by_first.setdefault(phrase[0], []).append((index, phrase, single))

    n = len(stream)
    cost = [10**9] * (n + 1)
    choice = [None] * n
    cost[n] = 0
    for i in range(n - 1, -1, -1):
        token = stream[i]
        for index, phrase, single in by_first.get(token, ()):
            end = i + len(phrase)
            if end <= n and tuple(stream[i:end]) == phrase:
                ref_cost = 1 if single else 2
                candidate = ref_cost + cost[end]
                key = (candidate, ref_cost, -len(phrase), index)
                old = choice[i]
                old_key = old[0] if old is not None else None
                if old_key is None or key < old_key:
                    cost[i] = candidate
                    choice[i] = (key, end, -index - 1)
        if token not in ring.STOLEN:
            key = (1 + cost[i + 1], 1, -1, token)
            old = choice[i]
            if old is None or key < old[0]:
                cost[i] = key[0]
                choice[i] = (key, i + 1, token)

    result = []
    i = 0
    while i < n:
        selected = choice[i]
        if selected is None:
            raise ValueError(f"no dictionary segmentation at token {i}")
        _, i, marker = selected
        result.append(marker)
    return result, phrases


def choose_optimal_segmentation(stream, source_selector):
    """Use the checked-in dictionary but segment the source globally."""
    _, phrases = source_selector(list(stream))
    return optimal_segment(stream, phrases)


def encoded_marker_cost(markers, phrases):
    return sum(
        1 if marker >= 0 or phrases[-marker - 1][1] else 2
        for marker in markers
    )


def choose_one_swap(stream, source_selector, pool_size=48):
    """Find the best single phrase swap without widening its P1 literal slot."""
    _, phrases = source_selector(list(stream))
    markers, _ = optimal_segment(stream, phrases)
    best_cost = encoded_marker_cost(markers, phrases)
    best = (markers, phrases)
    selected = {phrase for phrase, _ in phrases}
    raw_candidates = candidates(stream)

    pools = {}
    for single in (False, True):
        ref = 1 if single else 2
        ranked = sorted(
            (
                ((len(phrase) - ref) * hits, hits, phrase)
                for phrase, hits in raw_candidates.items()
                if (len(phrase) - ref) * hits > 0 and phrase not in selected
            ),
            reverse=True,
        )
        pools[single] = [phrase for _, _, phrase in ranked[:pool_size]]

    forced = {tuple([value]) for value in ring.STOLEN}
    for index, (old_phrase, single) in enumerate(phrases):
        if old_phrase in forced:
            continue
        old_digits = len(str(ring.pack128(ring.phrase_bytes(old_phrase))))
        for replacement in pools[single]:
            digits = len(str(ring.pack128(ring.phrase_bytes(replacement))))
            if digits > old_digits:
                continue
            trial = list(phrases)
            trial[index] = (replacement, single)
            trial_markers, _ = optimal_segment(stream, trial)
            trial_cost = encoded_marker_cost(trial_markers, trial)
            if trial_cost < best_cost:
                best_cost = trial_cost
                best = (trial_markers, trial)
    return best


def encode_with_selector(config, selector, ring_entries, group_b_rows, cap):
    threshold = config["threshold"]
    pair_slots = ring_entries - (threshold - 1)
    if pair_slots < len(config["stolen"]):
        raise ValueError("ring budget is smaller than the forced dictionary")

    old_selector = ring.choose_phrases
    with alphabet(config):
        def chosen(stream):
            key = (config["name"], selector, ring_entries)
            if key not in _SELECTION_CACHE:
                if selector == "source":
                    selected = old_selector(stream)
                elif selector == "optimal-seg":
                    selected = choose_optimal_segmentation(stream, old_selector)
                elif selector == "swap1":
                    selected = choose_one_swap(stream, old_selector)
                elif selector.startswith("weight="):
                    weight = float(selector.split("=", 1)[1])
                    selected = choose_weighted(
                        stream,
                        len(config["small_free"]),
                        pair_slots,
                        weight,
                    )
                else:
                    selected = choose_fixed(
                        stream,
                        len(config["small_free"]),
                        pair_slots,
                        selector,
                    )
                _SELECTION_CACHE[key] = selected
            selected_stream, selected_phrases = _SELECTION_CACHE[key]
            return list(selected_stream), list(selected_phrases)

        ring.choose_phrases = chosen
        try:
            symbols, values, layout = ring.build_encoding(
                bottom_up=True,
                group_b_rows=group_b_rows,
                group_a_cap=cap,
            )
        finally:
            ring.choose_phrases = old_selector

    group_a_rows = layout["group_a_rows"]
    group_b_width = sum(layout["TB"]) + 3 * len(layout["TB"])
    return {
        "config": config["name"],
        "selector": selector,
        "symbols": symbols,
        "ring": values,
        "layout": layout,
        "group_a_rows": group_a_rows,
        "group_b_rows": group_b_rows,
        "dictionary_rows": group_a_rows + group_b_rows,
        "group_b_width": group_b_width,
        "feasible": group_b_width <= cap,
    }


def summarize_encoding(result):
    return {
        key: result[key]
        for key in (
            "config", "selector", "symbols_count", "ring_entries",
            "group_a_rows", "group_b_rows", "dictionary_rows",
            "group_b_width", "feeder_width", "feeder_rows",
            "chunks", "max_used", "total_height", "box",
        )
        if key in result
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=79)
    parser.add_argument("--ring-entries", type=int, default=37)
    parser.add_argument("--dictionary-rows", type=int, default=7)
    parser.add_argument("--finalists", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # A 79-column P1 room leaves 72 source cells for literals, delimiters,
    # sends, and the turn/pump margin.
    cap = args.width - 7
    results = []
    specs = [
        (CONFIG_81, "source"),
        (CONFIG_80, "source"),
        (CONFIG_80, "optimal-seg"),
        (CONFIG_80, "swap1"),
        *((CONFIG_80, f"weight={weight}") for weight in
          ("0.25", "0.5", "0.75", "1", "1.25", "1.5")),
    ]
    for config, selector in specs:
        # The existing 80x80 dictionary uses four group-B rows.  Trying three
        # and five is cheap and catches a different width/height balance.
        for group_b_rows in (3, 4, 5):
            try:
                result = encode_with_selector(
                    config, selector, args.ring_entries, group_b_rows, cap
                )
            except (AssertionError, ValueError):
                continue
            if (
                result["feasible"]
                and result["dictionary_rows"] <= args.dictionary_rows
                and len(result["ring"]) <= args.ring_entries
            ):
                result["symbols_count"] = len(result["symbols"])
                result["ring_entries"] = len(result["ring"])
                results.append(result)

    # Deduplicate encodings before paying for exact feeder packing.
    unique = {}
    for result in results:
        key = tuple(result["symbols"])
        old = unique.get(key)
        geometry = (
            result["dictionary_rows"],
            result["group_b_width"],
            result["symbols_count"],
        )
        if old is None or geometry < (
            old["dictionary_rows"],
            old["group_b_width"],
            old["symbols_count"],
        ):
            unique[key] = result
    ranked = sorted(
        unique.values(),
        key=lambda r: (
            r["symbols_count"],
            r["dictionary_rows"],
            r["group_b_width"],
        ),
    )
    # Preserve the best stream at each dictionary height.  A one-row shorter
    # table can beat a shorter symbol stream even when its feeder is longer.
    finalists = []
    seen_rows = set()
    for result in ranked:
        if result["dictionary_rows"] not in seen_rows:
            finalists.append(result)
            seen_rows.add(result["dictionary_rows"])
    for result in ranked:
        if result not in finalists:
            finalists.append(result)
        if len(finalists) >= args.finalists:
            break
    finalists = finalists[:max(args.finalists, len(seen_rows))]

    for result in finalists:
        bands = ring.optimize_feeder(result["symbols"], args.width)
        result["feeder_width"] = args.width
        result["feeder_rows"] = sum(band.rows for band in bands)
        result["chunks"] = sum(len(band.chunks) for band in bands)
        result["max_used"] = max(band.required_width for band in bands)
        result["total_height"] = (
            result["feeder_rows"] + result["dictionary_rows"] + 12
        )
        result["box"] = max(args.width, result["total_height"]) ** 2

    finalists.sort(
        key=lambda r: (
            r["box"],
            r["total_height"],
            r["symbols_count"],
            r["chunks"],
        )
    )
    report = [summarize_encoding(result) for result in finalists]
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for item in report:
            print(
                "{config:5s} {selector:12s} symbols={symbols_count} "
                "ring={ring_entries} dict={group_a_rows}+{group_b_rows} "
                "width={group_b_width}/{feeder_width} "
                "feeder={feeder_rows} rows chunks={chunks} "
                "height={total_height} box={box} "
                "max-used={max_used}".format(**item)
            )


if __name__ == "__main__":
    main()
