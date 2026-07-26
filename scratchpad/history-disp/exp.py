#!/usr/bin/env python3
"""Fast experiment harness for the vertical-P1 DISP block.

Caches build_encoding() (the ~35 s feeder DP) so a DISP grid change costs a
sub-second rebuild.  Usage:

    python3 exp.py            # rebuild baseline into /tmp and grade it
"""
from __future__ import annotations

import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SOL = os.path.join(ROOT, "solutions", "history-lesson")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, SOL)

CACHE = os.path.join(HERE, "encoding.pkl")


def encoding():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    import build_vertical_p1 as p1
    data = p1.build_encoding()
    with open(CACHE, "wb") as fh:
        pickle.dump(data, fh)
    return data


if __name__ == "__main__":
    syms, ring, bands = encoding()
    print("symbols", len(syms), "ring", len(ring), "bands", len(bands))
