#!/usr/bin/env python3
"""Sweep pipe-free History Lesson geometry and prototype room folding.

This intentionally ignores pipe routing.  It computes exact feeder and
dictionary room dimensions, then asks whether those rectangles plus the four
service rooms can be packed inside a target square.  A reported fit is a
geometry candidate, not yet a runnable program.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import sys
from dataclasses import dataclass


HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.dirname(HERE)
sys.path[:0] = [HERE, HISTORY_DIR]

import build


@dataclass(frozen=True)
class Rect:
    name: str
    width: int
    height: int
    rotatable: bool = False


def parse_ints(spec: str) -> list[int]:
    values: set[int] = set()
    for part in spec.split(","):
        fields = part.split("-")
        if len(fields) == 1:
            values.add(int(fields[0]))
        elif len(fields) == 2:
            start, stop = map(int, fields)
            values.update(range(start, stop + 1))
        else:
            raise ValueError(f"invalid integer range: {part!r}")
    return sorted(values)


def orientations(rect: Rect):
    yield rect.width, rect.height
    if rect.rotatable and rect.width != rect.height:
        yield rect.height, rect.width


def pack_rectangles(
    feeder_width: int,
    feeder_height: int,
    other_rectangles: list[Rect],
    target: int,
):
    """Return one edge-aligned non-overlapping packing, if one exists."""
    if feeder_width > target or feeder_height > target:
        return None
    placed = [("feeder", 0, 0, feeder_width, feeder_height)]
    remaining = sorted(
        other_rectangles,
        key=lambda rect: (rect.width * rect.height, max(rect.width, rect.height)),
        reverse=True,
    )

    def search(index: int):
        if index == len(remaining):
            return tuple(placed)
        rect = remaining[index]
        xs = sorted({0, *(x + width for _, x, _, width, _ in placed)})
        ys = sorted({0, *(y + height for _, _, y, _, height in placed)})
        for width, height in orientations(rect):
            for y in ys:
                if y + height > target:
                    continue
                for x in xs:
                    if x + width > target:
                        continue
                    if any(
                        x < px + pw
                        and px < x + width
                        and y < py + ph
                        and py < y + height
                        for _, px, py, pw, ph in placed
                    ):
                        continue
                    placed.append((rect.name, x, y, width, height))
                    result = search(index + 1)
                    if result is not None:
                        return result
                    placed.pop()
        return None

    return search(0)


def feeder_job(job):
    words, feeder_width, catalog_path = job
    logging.disable(logging.CRITICAL)
    catalog = build.raw_dictionary.load_catalog(catalog_path)
    symbols, ring, _ = build.raw_dictionary.build_encoding(
        build.vertical.base.TEXT,
        words,
        catalog,
    )
    bands = build.vertical.base.optimize_feeder(symbols, feeder_width)
    return words, feeder_width, sum(band.rows for band in bands) + 2, ring


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", default="17-91")
    parser.add_argument("--feeder-widths", default="60,65,70,75,80")
    parser.add_argument("--dictionary-widths", default="13-60")
    parser.add_argument("--target", type=int, default=80)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument(
        "--catalog",
        default=build.raw_dictionary.CATALOG_PATH,
    )
    parser.add_argument(
        "--allow-rotations",
        action="store_true",
        help="also prototype rotating dictionary and service rooms",
    )
    args = parser.parse_args()

    words_values = parse_ints(args.words)
    feeder_widths = parse_ints(args.feeder_widths)
    dictionary_widths = parse_ints(args.dictionary_widths)
    jobs = [
        (words, feeder_width, args.catalog)
        for words in words_values
        for feeder_width in feeder_widths
    ]

    service_rectangles = [
        Rect("decoder", 11, 4, args.allow_rotations),
        Rect("unpack", 12, 4, args.allow_rotations),
        Rect("output", 3, 3, False),
        Rect("dispatcher", 23, 7, args.allow_rotations),
    ]
    results = []
    feeder_sizes = set()
    if args.jobs == 1:
        feeder_results = map(feeder_job, jobs)
    else:
        pool = concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs)
        feeder_results = pool.map(feeder_job, jobs)
    try:
        for words, feeder_width, feeder_height, ring in feeder_results:
            feeder_sizes.add((words, feeder_width, feeder_height))
            values = [ring[position] for position in sorted(ring)]
            for dictionary_width in dictionary_widths:
                try:
                    dictionary_bands = build.pack_dictionary(
                        values,
                        dictionary_width,
                    )
                except ValueError:
                    continue
                dictionary_height = 2 * len(dictionary_bands) + 2
                rectangles = [
                    Rect(
                        "dictionary",
                        dictionary_width,
                        dictionary_height,
                        args.allow_rotations,
                    ),
                    *service_rectangles,
                ]
                packing = pack_rectangles(
                    feeder_width,
                    feeder_height,
                    rectangles,
                    args.target,
                )
                if packing is not None:
                    results.append(
                        (
                            words,
                            feeder_width,
                            feeder_height,
                            dictionary_width,
                            dictionary_height,
                            packing,
                        )
                    )
    finally:
        if args.jobs != 1:
            pool.shutdown()

    print("feeder dimensions:")
    for words, width, height in sorted(feeder_sizes):
        print(f"  words={words} feeder={width}x{height}")
    print(
        "words\tfeeder\tfeeder_h\tdictionary\tdictionary_h\tpacking"
    )
    for words, fw, fh, dw, dh, packing in sorted(results):
        cells = ";".join(
            f"{name}@{x},{y}:{width}x{height}"
            for name, x, y, width, height in packing
        )
        print(f"{words}\t{fw}\t{fh}\t{dw}\t{dh}\t{cells}")
    print(f"fits={len(results)} jobs={len(jobs)} target={args.target}")


if __name__ == "__main__":
    main()
