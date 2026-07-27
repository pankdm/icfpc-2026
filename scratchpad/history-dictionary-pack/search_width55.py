#!/usr/bin/env python3
"""Prototype exact paired-slot bin packing for the 55-column dictionary."""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUILDER = os.path.join(ROOT, "solutions", "history-lesson", "layout-builder")
sys.path.insert(0, BUILDER)

import build
import dictionary


def pair_positions(positions, ring):
    ordered = sorted(positions, key=lambda p: (-len(str(ring[p])), p))
    return list(zip(ordered[::2], ordered[1::2]))


def partition(items, capacities):
    bins = [[] for _ in capacities]

    def visit(index):
        if index == len(items):
            return True
        item = items[index]
        cost = item[2]
        tried = set()
        for bin_index, capacity in enumerate(capacities):
            used = sum(entry[2] for entry in bins[bin_index])
            remaining = capacity - used
            if remaining < cost or remaining in tried:
                continue
            tried.add(remaining)
            bins[bin_index].append(item)
            if visit(index + 1):
                return True
            bins[bin_index].pop()
        return False

    if not visit(0):
        return None
    return bins


def class_order(positions, ring, capacities):
    pairs = pair_positions(positions, ring)
    items = sorted(
        (
            (top, bottom, len(str(ring[top])) + 3)
            for top, bottom in pairs
        ),
        key=lambda item: (-item[2], item[0], item[1]),
    )
    bins = partition(items, capacities)
    if bins is None:
        return None
    order = []
    for entries in bins:
        order.extend(top for top, _, _ in entries)
        order.extend(bottom for _, bottom, _ in reversed(entries))
    return order, bins


def main():
    catalog = dictionary.load_catalog(
        os.path.join(BUILDER, "dictionary_words_layout_gain.json")
    )
    symbols, ring, _ = dictionary.build_encoding(
        build.vertical.base.TEXT,
        52,
        catalog,
    )
    direct = class_order(range(1, 17), ring, [46, 49])
    escaped = class_order(range(17, 53), ring, [49, 49, 49, 49, 46])
    print("direct", direct)
    print("escaped", escaped)
    if direct is None or escaped is None:
        raise SystemExit(1)
    order = direct[0] + escaped[0]
    rewritten, new_ring, _ = build._rewrite_physical_dictionary(
        symbols,
        ring,
        order,
    )
    bands = build.pack_dictionary(
        [new_ring[position] for position in range(1, 53)],
        55,
        preload_bp2=True,
    )
    print("order", order)
    print("bands", len(bands), [band.constant_count for band in bands])
    print("widths", [sum(width + 3 for width in band.widths) for band in bands])
    assert len(bands) == 7
    codes, _ = build.compact_alphabet(rewritten)
    assert all(1 <= code <= 63 for code in codes)


if __name__ == "__main__":
    main()
