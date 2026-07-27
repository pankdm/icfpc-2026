#!/usr/bin/env python3
"""Report vertical/horizontal backtick pairs whose span is not digits+spaces.

The organiser oracle rejects those ("expected a digit or a space between
backticks"); the Rust engine silently treats them as "not a literal", so this
divergence only shows up as a submission load error.

usage: python3 scratchpad/cf_lint.py <file.man> [--rooms]
"""
import sys


def main():
    path = sys.argv[1]
    rows = open(path, encoding="utf-8").read().split("\n")
    h = len(rows)
    w = max(len(r) for r in rows)
    g = [r.ljust(w) for r in rows]

    def at(x, y):
        return g[y][x]

    def scan(cells, label):
        ticks = [i for i, c in enumerate(cells) if c == "`"]
        out = []
        i = 0
        while i + 1 < len(ticks):
            a, b = ticks[i], ticks[i + 1]
            span = cells[a + 1:b]
            bad = [c for c in span if c != " " and not c.isdigit()]
            if bad:
                out.append((label, a, b, "".join(span)[:40]))
            i += 2
        return out

    bad = []
    for x in range(w):
        bad += scan([at(x, y) for y in range(h)], "col %d" % x)
    for y in range(h):
        bad += scan(list(g[y]), "row %d" % y)
    print("dirty pairs:", len(bad))
    for b in bad[:25]:
        print("  ", b)


main()
