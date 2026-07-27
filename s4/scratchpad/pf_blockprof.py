#!/usr/bin/env python3
"""Attribute every controller tick to a BLOCK and an OP INDEX of the flow.

`lm --profile` gives per-cell execution counts; railflow's layout gives each
block's entry row and `_lay_once` walks the ops in order, so replaying the
placement records exactly which (x,y) each token landed on.  Joining the two
turns "385,910 ticks of rr stall" into "which `load()` in which block".

  cd s4 && python3 scratchpad/pf_blockprof.py /tmp/pf_prof.txt <ctrl_max_y>
"""
import ast
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import boustro  # noqa: E402
import build_bitset6  # noqa: E402
import railflow  # noqa: E402
import stateflow  # noqa: E402
from build_reflow_banked import alias_empty_gotos  # noqa: E402

CFG = json.load(open(os.path.join(FORK, "solutions", "pathfinder",
                                  "dense-f.json")))
FLOW = alias_empty_gotos(build_bitset6.build_flow())

# --- replay the placement, recording (x,y) -> (block, op index, token) ------
SITE = {}
_ctx = {"label": None, "i": 0}
_orig_place = boustro.Cursor.place
_orig_run = boustro.Cursor.place_run


def _place(self, ch, lo, hi):
    _orig_place(self, ch, lo, hi)
    SITE[(self.x, self.y)] = (_ctx["label"], _ctx["i"], ch)


def _run(self, chars, lo, hi):
    _orig_run(self, chars, lo, hi)
    SITE[(self.x, self.y)] = (_ctx["label"], _ctx["i"], chars)


boustro.Cursor.place = _place
boustro.Cursor.place_run = _run

_orig_lay = railflow._lay_once


def _lay(flow, *a, **kw):
    """Same walk as railflow._lay_once but announcing (label, op index)."""
    class Blocks(dict):
        def __getitem__(self, label):
            _ctx["label"] = label
            toks = dict.__getitem__(self, label)

            class Seq(list):
                def __iter__(self):
                    for i, t in enumerate(toks):
                        _ctx["i"] = i
                        yield t
            return Seq(toks)
    saved = flow.blocks
    flow.blocks = Blocks(saved)
    try:
        return _orig_lay(flow, *a, **kw)
    finally:
        flow.blocks = saved


railflow._lay_once = _lay


def main():
    txt = open(sys.argv[1]).read()
    ctrl_max_y = int(sys.argv[2])
    ports = CFG["ports"]
    spec = {n: (ports[n], stateflow.DEFAULT_PORTS[n][1]) for n in ports}
    cols = {n: spec[n][0] for n in spec}
    glyphs = {n: spec[n][1] for n in spec}
    bands = {}
    for g in ("s", "r"):
        bands.update(boustro.voronoi_bands(
            [(n, c) for n, c in cols.items() if glyphs[n] == g]))
    forbid = set(range(40, 70)) | set(range(156, 184))
    labels = list(FLOW.blocks)
    railflow.lay_cfg_rail.__wrapped__ if False else None
    import littleman as lm
    p = lm.Program()
    railflow.lay_cfg_rail(p, FLOW, spec, code_x=0, op_slack=0,
                          lit_forbid=forbid)

    cells = ast.literal_eval(re.search(
        r"PROFILE cells=(\[.*?\])\n(?=PROFILE|\Z)", txt, re.S).group(1))
    stalls = dict(ast.literal_eval(re.search(
        r"PROFILE stalls=(\[.*?\])\n(?=PROFILE|\Z)", txt, re.S).group(1)))

    by_block = Counter()
    by_site = []
    unmapped = 0
    for (x, y), n in cells:
        if y > ctrl_max_y:
            continue
        site = SITE.get((x, y))
        if site is None:
            unmapped += n
            continue
        by_block[site[0]] += n
        by_site.append((n, stalls.get((x, y), 0), site, (x, y)))
    by_site.sort(reverse=True)
    print(f"mapped {sum(by_block.values()):,} ticks, unmapped(glide/rails) "
          f"{unmapped:,}")
    print("\nticks by block:")
    for lab, n in by_block.most_common(14):
        print(f"  {n:8,}  {lab}")
    print("\ntop op sites (ticks, stall, block, op#, token):")
    for n, st, site, pos in by_site[:22]:
        toks = FLOW.blocks[site[0]]
        near = toks[max(0, site[1] - 2):site[1] + 2]
        print(f"  {n:7,} {st:7,}  {site[0]:<16} #{site[1]:<3} {site[2]!r:4} "
              f"ctx {near}")


main()
