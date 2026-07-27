#!/usr/bin/env python3
"""Report the six-row T=23 dictionary frontier without running feeder DP."""
from __future__ import annotations

import sys

sys.path[:0] = ["solutions/history-lesson", "tools"]

import build_ring as ring
import search_feeder_dictionary as search


LOW_CODES = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]


def main() -> None:
    weight = float(sys.argv[1])
    ring.THRESHOLD = 23
    ring.ESC = 29
    ring.SMALL_FREE = LOW_CODES
    ring.STOLEN = (8, 18, 23)

    def selector(stream):
        return search.choose_weighted(
            stream,
            single_slots=15,
            pair_slots=15,
            table_weight=weight,
        )

    try:
        symbols, _, layout = ring.build_encoding(
            threshold=23,
            west_first=True,
            group_b_rows=3,
            group_a_cap=72,
            phrase_selector=selector,
        )
    except (AssertionError, ValueError) as error:
        print(f"{weight:.4f} infeasible {type(error).__name__}: {error}")
        return
    width = sum(layout["TB"]) + 3 * len(layout["TB"])
    print(
        f"{weight:.4f} symbols={len(symbols)} "
        f"A={layout['group_a_rows']} B={layout['group_b_rows']} width={width}"
    )


if __name__ == "__main__":
    main()
