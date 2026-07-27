#!/usr/bin/env python3
"""Sweep compact folded candidates where runtime is irrelevant and size wins."""
from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os

import build
from sweep_geometry import parse_ints

HERE = os.path.dirname(os.path.abspath(__file__))


def evaluate(job):
    words, feeder_width, dictionary_width, catalog_path = job
    logging.disable(logging.CRITICAL)
    catalog = build.raw_dictionary.load_catalog(catalog_path)
    symbols, ring, _ = build.raw_dictionary.build_encoding(
        build.vertical.base.TEXT,
        words,
        catalog,
    )
    try:
        symbols, ring, _, dictionary_bands = (
            build.repack_physical_dictionary(
                symbols,
                ring,
                dictionary_width,
                preload_bp2=True,
            )
        )
    except ValueError:
        return words, None
    codes, _ = build.compact_alphabet(symbols)
    feeder_bands = build.vertical.base.optimize_feeder(
        codes,
        feeder_width,
        base=64,
    )
    return words, {
        "codes": len(codes),
        "feeder_rows": sum(band.rows for band in feeder_bands),
        "dictionary_bands": len(dictionary_bands),
        "dictionary_rows": 2 * len(dictionary_bands) + 2,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", default="42-60")
    parser.add_argument("--feeder-width", type=int, default=80)
    parser.add_argument("--dictionary-width", type=int, default=55)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument(
        "--catalog",
        default=os.path.join(HERE, "dictionary_words_layout_gain.json"),
    )
    args = parser.parse_args()
    jobs = [
        (
            words,
            args.feeder_width,
            args.dictionary_width,
            args.catalog,
        )
        for words in parse_ints(args.words)
    ]
    if args.jobs == 1:
        results = list(map(evaluate, jobs))
    else:
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=args.jobs
        ) as pool:
            results = list(pool.map(evaluate, jobs))
    print("words\tcodes\tfeeder_rows\tdictionary_bands\tdictionary_rows")
    for words, result in results:
        if result is None:
            print(f"{words}\t-\t-\t-\t-")
        else:
            print(
                f"{words}\t{result['codes']}\t{result['feeder_rows']}\t"
                f"{result['dictionary_bands']}\t"
                f"{result['dictionary_rows']}"
            )


if __name__ == "__main__":
    main()
