#!/usr/bin/env python3
"""Exact tick model for the generated LLLM interpreter.

WHY THIS EXISTS.  `grade_fast` on this slug costs 55s for the ten public cases,
which is far too slow to search geometry with.  But the controller man never
stalls -- profiling `around the block` shows the controller room executing
966,763 cells against a settle tick of 968,404, i.e. **ticks == cells walked**,
and 847,658 of those cells (87.7%) are BLANK.  The program is not pipe-bound at
all; it is bound by how far the man walks between ports.

So the whole score is a function of geometry that we can compute:

    ticks(case) = SUM over executed (block, exit) of
                    cum[block][exit_index] + exit[(block, exit_index)]

`cum`/`exit` come from CodePlacer (cells stepped inside a block, and cells
stepped leaving it), the execution counts come from lllm_sim.py.  Validated
against the Rust engine below -- run this file to see the residual.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import lllm_flow as F
import lllm_sim as S
import build_lllm as B
import layout as lay
import littleman as lm


class TracingSim(S.Sim):
    """Records (label, index of the token that ended the block) per execution."""

    def run(self, want_frames, limit=40_000_000):
        self.hits = Counter()
        blocks = self.flow.blocks
        order = self.flow.order
        nxt = {order[i]: order[i + 1] for i in range(len(order) - 1)}
        label = order[0]
        while True:
            toks = blocks[label]
            jump = None
            for ti, tok in enumerate(toks):
                self.steps += 1
                if self.steps > limit:
                    raise RuntimeError("step limit in block %s" % label)
                jump = self.exec_tok(tok, label)
                if jump is not None:
                    self.hits[(label, ti)] += 1
                    break
                if len(self.disp.frames) >= want_frames:
                    self.hits[(label, ti)] += 1
                    return self.disp.frames
            if len(self.disp.frames) >= want_frames:
                return self.disp.frames
            if jump is None:
                raise RuntimeError("fell off the end at %s" % label)
            label = jump


def case_hits(rounds, flow=None):
    flow = flow or F.build_flow()
    vals = [int(v) for r in rounds for v in r]
    sim = TracingSim(flow, vals)
    sim.run(len(rounds))
    return sim.hits


def all_hits(spec=None):
    """[(name, Counter)] for every public case -- geometry-independent, so this
    is computed ONCE and reused for every candidate layout."""
    import json
    spec = spec or json.load(open(os.path.join(
        HERE, "..", "..", "tests", "little-little-little-man.json")))
    flow = F.build_flow()
    out = []
    for case in spec["publicTestData"]:
        rounds = [r["in"] for r in case["rounds"]]
        out.append((case.get("name"), case_hits(rounds, flow)))
    return out


def placer_costs(holder_order=None, blocks=None, **kw):
    """(cum, exit) for a candidate geometry, without drawing the whole program."""
    if blocks is None:
        blocks = B.split_blocks(F.build_flow())
    holder_order = holder_order or B.HOLDER_ORDER
    cols = B.Columns(blocks, holder_order,
                     lanes=B.plan_lanes(blocks, holder_order, **kw), **kw)
    g = lay.Layout(lm.Program())
    placer = B.CodePlacer(g, cols, 1)
    placer.place(blocks)
    placer.finish()
    return placer, cols


def ticks(hits, placer):
    t = 0
    for (label, ti), n in hits.items():
        t += n * (placer.cum[label][ti] + placer.exit.get((label, ti), 0))
    return t


def avg_ticks(hits_all, placer):
    return sum(ticks(h, placer) for _n, h in hits_all) / float(len(hits_all))


def main():
    hits_all = all_hits()
    placer, cols = placer_costs()
    measured = {
        "one tick at a time": 303002, "first steps": 71406,
        "around the block": 968404, "off the edge": 290032,
        "widdershins": 493302, "crossroads": 366114,
        "revolving door": 119426, "swan dive": 174114,
        "hall of mirrors": 481958, "victory lap": 849086,
    }
    print("%-22s %10s %10s %8s" % ("case", "model", "rust", "resid"))
    tot_m = tot_r = 0
    for name, h in hits_all:
        m = ticks(h, placer)
        r = measured[name]
        tot_m += m
        tot_r += r
        print("%-22s %10d %10d %7.2f%%" % (name, m, r, 100.0 * (m - r) / r))
    print("%-22s %10.1f %10.1f %7.2f%%" % ("AVERAGE", tot_m / 10.0, tot_r / 10.0,
                                           100.0 * (tot_m - tot_r) / tot_r))


if __name__ == "__main__":
    main()
