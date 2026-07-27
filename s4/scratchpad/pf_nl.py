#!/usr/bin/env python3
"""Attribute every controller newline in the pathfinder champion layout."""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import boustro  # noqa: E402
import stateflow  # noqa: E402
import build_rail  # noqa: E402

CFG = json.load(open(os.path.join(FORK, "solutions", "pathfinder",
                                  "dense-e.json")))

S = {"cur": None, "prev": None}
NL = Counter()
PLACED = Counter()

_orig_nl = boustro.Cursor.newline
_orig_place = boustro.Cursor.place


def newline(self):
    NL[(S["prev"], S["cur"])] += 1
    _orig_nl(self)


def place(self, ch, lo, hi):
    S["cur"] = (ch, lo, hi)
    _orig_place(self, ch, lo, hi)
    PLACED[(ch, lo, hi)] += 1
    S["prev"] = S["cur"]


boustro.Cursor.newline = newline
boustro.Cursor.place = place


def main():
    shape = dict(CFG["floor"])
    qrows = shape.pop("queue_rows", 1)
    qright = shape.pop("queue_right_off", 300)
    ports = CFG["ports"]
    spec = {n: (ports[n], stateflow.DEFAULT_PORTS[n][1]) for n in ports}
    program, layout = build_rail.build(
        verify=False, ports=spec, floor=shape,
        queue_rows=qrows, queue_right_off=qright)
    w, h, box = program.footprint()
    print(f"{w}x{h} box {box:,} ctrl {layout['width']}x{layout['height']} "
          f"rail {layout['ncorr']}")
    name = {}
    for port, (lo, hi) in layout["bands"].items():
        name[(lo, hi)] = port
    print("bands:", sorted(layout["bands"].items(), key=lambda kv: kv[1]))

    def tag(t):
        if t is None:
            return "-"
        ch, lo, hi = t
        return name.get((lo, hi), f"op:{ch}")
    print("placed ops", sum(PLACED.values()))
    print("newlines total", sum(NL.values()))
    agg = Counter()
    for (a, b), v in NL.items():
        agg[(tag(a), tag(b))] += v
    for k, v in agg.most_common(20):
        print(f"  {v:4d}  {k[0]} -> {k[1]}")


main()
