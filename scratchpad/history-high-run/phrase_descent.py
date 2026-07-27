#!/usr/bin/env python3
"""Width-preserving phrase descent for the 79x79 History Lesson search.

The earlier search optimized code assignment after freezing a greedily chosen
phrase set.  This script keeps that assignment's exact six-row table geometry
and swaps phrases for equal-or-narrower literals.  It globally re-segments the
source after every swap, ranks all one-swap neighbours with the cheap feeder
proxy, and exact-packs the best distinct symbol streams.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HISTORY = os.path.join(ROOT, "solutions", "history-lesson")
sys.path[:0] = [HISTORY, os.path.join(ROOT, "tools")]

import build_ring as base
import search_feeder_dictionary as dictionary
from assign_search import HIGH_CODES, LOW_CODES, proxy

ESC = 29
PAIR_CODES = tuple(range(29, 38))


def packed(pattern):
    return base.pack128(base.phrase_bytes(pattern))


def digits(pattern):
    return len(str(packed(pattern)))


def phrase_tokens(word):
    """Invert ``phrase_bytes`` (token 13 spells the two bytes ``, ``)."""
    data = word.encode("ascii")
    result = []
    index = 0
    while index < len(data):
        if data[index:index + 2] == b", ":
            result.append(13)
            index += 2
        else:
            result.append(data[index] - 31)
            index += 1
    return tuple(result)


def load_start():
    resumed = os.path.join(HERE, "phrase_descent.json")
    if "--resume" in sys.argv and os.path.exists(resumed):
        with open(resumed) as handle:
            result = json.load(handle)
        return [
            (phrase_tokens(item["phrase"]), tuple(item["emitted"]))
            for item in result["phrases"]
        ]

    with open(os.path.join(HERE, "assignment.json")) as handle:
        assignment = json.load(handle)

    phrases = (
        [(phrase_tokens(word), (code,)) for word, code in
         zip(assignment["low"], LOW_CODES)]
        + [(phrase_tokens(word), (code,)) for word, code in
           zip(assignment["high"], HIGH_CODES)]
        + [(phrase_tokens(word), (ESC, code)) for word, code in
           zip(assignment["pairs"], PAIR_CODES)]
    )
    return phrases


def segment(phrases):
    """Globally shortest segmentation, with deterministic code-order ties."""
    stream = base.tokenize(base.TEXT)
    by_first = {}
    for index, (phrase, emitted) in enumerate(phrases):
        by_first.setdefault(phrase[0], []).append((index, phrase, emitted))

    forbidden = {8, 18, 23}
    n = len(stream)
    cost = [10**9] * (n + 1)
    choice = [None] * n
    cost[n] = 0
    for i in range(n - 1, -1, -1):
        token = stream[i]
        if token not in forbidden:
            choice[i] = ((1 + cost[i + 1], 1, token), i + 1, (token,))
            cost[i] = 1 + cost[i + 1]
        for index, phrase, emitted in by_first.get(token, ()):
            end = i + len(phrase)
            if end > n or tuple(stream[i:end]) != phrase:
                continue
            candidate = len(emitted) + cost[end]
            key = (candidate, len(emitted), -len(phrase), emitted, index)
            if choice[i] is None or key < choice[i][0]:
                cost[i] = candidate
                choice[i] = (key, end, emitted)
    symbols = []
    i = 0
    while i < n:
        if choice[i] is None:
            raise ValueError(f"source is not segmentable at {i}")
        _, i, emitted = choice[i]
        symbols.extend(emitted)
    return symbols


def candidate_pool():
    stream = base.tokenize(base.TEXT)
    old = (base.THRESHOLD, base.ESC, base.STOLEN)
    base.THRESHOLD, base.ESC, base.STOLEN = 23, ESC, (8, 18, 23)
    try:
        found = dictionary.candidates(stream)
    finally:
        base.THRESHOLD, base.ESC, base.STOLEN = old
    ranked = sorted(
        found,
        key=lambda phrase: (
            -(len(phrase) - 1) * found[phrase],
            digits(phrase),
            -len(phrase),
            phrase,
        ),
    )
    return ranked


def neighbour_job(job):
    phrases, slot, replacement = job
    trial = list(phrases)
    trial[slot] = (replacement, trial[slot][1])
    symbols = segment(trial)
    return proxy(symbols), len(symbols), slot, replacement, symbols, trial


def exact_job(item):
    key, symbols, phrases = item
    bands = base.optimize_feeder(symbols, 79)
    return (
        sum(band.rows for band in bands),
        sum(len(band.chunks) for band in bands),
        key,
        symbols,
        phrases,
    )


def printable(phrases):
    return [
        {
            "phrase": base.phrase_bytes(phrase).decode("ascii"),
            "emitted": list(emitted),
            "digits": digits(phrase),
        }
        for phrase, emitted in phrases
    ]


def main():
    phrases = load_start()
    pool = candidate_pool()
    forced = {
        tuple([value])
        for value in (8, 18, 23)
    }
    best_streams = {}

    for round_index in range(8):
        selected = {phrase for phrase, _ in phrases}
        jobs = []
        for slot, (old_phrase, emitted) in enumerate(phrases):
            if old_phrase in forced:
                continue
            cap = digits(old_phrase)
            # Direct slots benefit from two-character phrases too; escaped
            # slots need length >= 3 to save any stream symbols.
            minimum = 2 if len(emitted) == 1 else 3
            eligible = [
                phrase for phrase in pool
                if phrase not in selected
                and len(phrase) >= minimum
                and digits(phrase) <= cap
            ][:160]
            jobs.extend((phrases, slot, phrase) for phrase in eligible)

        with multiprocessing.Pool(4) as workers:
            results = list(workers.imap_unordered(
                neighbour_job, jobs, chunksize=8
            ))
        results.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        baseline_symbols = segment(phrases)
        baseline = (proxy(baseline_symbols), len(baseline_symbols))
        print(
            f"round={round_index} baseline={baseline} "
            f"neighbours={len(results)} best={results[0][:2]}",
            flush=True,
        )

        # Preserve several proxy shapes for the expensive exact DP.  A proxy
        # regression can still improve exact packing, so retain more than only
        # the accepted move.
        for result in results[:32]:
            key, count, _, _, symbols, trial = result
            best_streams.setdefault(tuple(symbols), ((key, count), symbols, trial))

        winner = results[0]
        if winner[:2] >= baseline:
            break
        phrases = winner[5]

    ranked = sorted(best_streams.values(), key=lambda item: item[0])[:24]
    print(f"exact finalists={len(ranked)}", flush=True)
    with multiprocessing.Pool(4) as workers:
        exact = list(workers.imap_unordered(exact_job, ranked))
    exact.sort(key=lambda item: item[:3])
    for result in exact[:12]:
        print("exact", result[:3], flush=True)

    winner = exact[0]
    output = {
        "rows": winner[0],
        "chunks": winner[1],
        "proxy": winner[2],
        "symbols": len(winner[3]),
        "phrases": printable(winner[4]),
    }
    with open(os.path.join(HERE, "phrase_descent.json"), "w") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    print(json.dumps(output, indent=2))
    return 0 if winner[0] <= 61 else 1


if __name__ == "__main__":
    raise SystemExit(main())
