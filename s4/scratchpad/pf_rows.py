#!/usr/bin/env python3
"""Where do pathfinder's controller rows come from?

Splits the rail layout's row count into: 1 row per block (floor), 1 per branch
(rail row), and everything else = band conflicts (a newline inside a block).
Also reports per-port op counts, so we can see which ports are worth merging.

    cd s4 && python3 scratchpad/pf_rows.py
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import stateflow  # noqa: E402
import build_bitset5  # noqa: E402
from build_reflow_banked import alias_empty_gotos  # noqa: E402


def main():
    flow = alias_empty_gotos(build_bitset5.build_flow())
    labels = list(flow.blocks)
    nblocks = len(labels)
    nbr = sum(1 for lb in labels
              if any(isinstance(t, tuple) and t[0] == "br"
                     for t in flow.blocks[lb]))
    ngo = sum(1 for lb in labels
              if any(isinstance(t, tuple) and t[0] == "go"
                     for t in flow.blocks[lb]))
    ops = Counter()
    nops = 0
    for lb in labels:
        for t in flow.blocks[lb]:
            if isinstance(t, tuple):
                continue
            nops += 1
            ops[t] += 1
    print(f"blocks {nblocks}  branches {nbr}  gotos {ngo}  ops {nops}")
    print("op histogram (top 30):", ops.most_common(30))
    # which ops are port ops?
    print("\nports in DEFAULT_PORTS:", list(stateflow.DEFAULT_PORTS))


if __name__ == "__main__":
    main()
