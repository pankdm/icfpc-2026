#!/usr/bin/env python3
"""Stats on pathfinder's CFG: blocks, ops, terminators, fusion potential."""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import build_bitset5  # noqa: E402
from build_reflow_banked import alias_empty_gotos  # noqa: E402

flow = alias_empty_gotos(build_bitset5.build_flow())
labels = list(flow.blocks)
nops = 0
nterm = Counter()
preds = Counter()
succs = {}
for lab, toks in flow.blocks.items():
    body = [t for t in toks if not isinstance(t, tuple)]
    term = [t for t in toks if isinstance(t, tuple)]
    nops += len(body)
    if term:
        nterm[term[0][0]] += 1
        succs[lab] = term[0][1:]
        for t in dict.fromkeys(term[0][1:]):
            preds[t] += 1
    else:
        nterm["fall"] += 1
        succs[lab] = ()

print("blocks", len(labels), "ops", nops, "terms", dict(nterm))
sizes = Counter(len([t for t in v if not isinstance(t, tuple)])
                for v in flow.blocks.values())
print("block-size hist", sorted(sizes.items())[:15])
# fusion: go-terminated block whose target has exactly 1 predecessor
fusible = [l for l in labels
           if succs[l] and len(succs[l]) == 1 and preds[succs[l][0]] == 1
           and succs[l][0] != labels[0]]
print("fusible go-chains", len(fusible))
# unreached / dead
print("blocks with 0 preds", sum(1 for l in labels[1:] if preds[l] == 0))
# how many ops per block on average
print("avg ops/block", nops / len(labels))
