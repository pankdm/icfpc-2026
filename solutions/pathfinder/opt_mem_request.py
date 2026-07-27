#!/usr/bin/env python3
"""Shorten the complete Pathfinder's controller-to-MEM16 request pipe.

The pipe leaves the controller near (61,164), drops to row 166, then travels
west to the MEM16 hub's bottom wall at x=17.  The hub has only one incoming pipe, so
its receive operations do not depend on that attachment column.  Reattaching at
x=29 (the last non-corner wall cell) removes twelve latency cells without
changing any instruction or binding.
"""

from pathlib import Path
import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()

    rows = [list(row) for row in Path(args.source).read_text().splitlines()]
    width = max(map(len, rows))
    for row in rows:
        row.extend(" " * (width - len(row)))

    assert rows[165][17] == "^"
    assert rows[165][29] == " "
    assert rows[166][17] == "^"
    assert all(rows[166][x] == "-" for x in range(18, 61))
    assert rows[166][61] == "<"

    rows[165][17] = " "
    rows[165][29] = "^"
    for x in range(17, 29):
        rows[166][x] = " "
    rows[166][29] = "^"

    rendered = "\n".join("".join(row).rstrip() for row in rows) + "\n"
    Path(args.output).write_text(rendered)


if __name__ == "__main__":
    main()
