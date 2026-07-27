#!/usr/bin/env python3
"""Empirically measure controller rows as removable loads are stripped.

Not semantics-preserving -- purely a geometry probe: delete the token
subsequence of each avoidable load(addr) and re-run the real boustrophedon
layout to see what the row count actually does.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "solutions", "little-little-man"))

import boustro
import flowgrid
import littleman as lm
import build_banked_dedup as dedup
import build_banked_boustro as bb
import llm_load_bound as bound

PORT_SPEC = {
    "ri": (10, "r", 1, 19),
    "rp": (30, "r", 21, 51),
    "rr": (74, "r", 53, 152),
    "cr": (230, "r", 153, 240),
    "sp": (20, "s", 1, 34),
    "sc": (50, "s", 36, 64),
    "sd": (80, "s", 66, 98),
    "sa": (118, "s", 100, 149),
    "ss": (180, "s", 150, 189),
    "cc": (200, "s", 191, 240),
}


def analyse():
    flow = bb.alias_empty_gotos(dedup.build_flow())
    loads, stores, ram_touched = [], [], {}
    for label, toks in flow.blocks.items():
        bound.run_block(label, toks, loads, stores, ram_touched)
    return flow, loads


def load_pattern(addr):
    return ["0", "sc"] + flowgrid.const_ops(addr) + ["sc", "rr"]


def strip(flow, drop_idx):
    """Return a copy of *flow* with the given (block, indices) removed."""
    new = flowgrid.Flow()
    for label, toks in flow.blocks.items():
        drop = drop_idx.get(label, set())
        new.blocks[label] = [t for i, t in enumerate(toks) if i not in drop]
    return new


def measure(flow, code_x=45, op_slack=0):
    program = lm.Program()
    result = boustro.lay_cfg_boustrophedon(
        program, flow, PORT_SPEC, code_x=code_x, op_slack=op_slack)
    return result["width"], result["height"]


def main():
    flow, loads = analyse()

    # classify exactly as llm_load_bound does
    import llm_load_bound
    removable_cats = {"REGISTER_RESIDENT", "REDUNDANT",
                      "HOISTABLE(cross-block)", "HOISTABLE(loop-invariant)"}

    # re-run the full classifier to get categories
    sys.argv = ["x"]
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        loads2, stores2, blocks2 = llm_load_bound.main()

    by_key = {(e["block"], e["idx"]): e for e in loads2}

    # map each removable scalar load to its exact token range
    def ranges_for(pred):
        drop = {}
        hits = misses = 0
        for label, toks in flow.blocks.items():
            for i, t in enumerate(toks):
                if t != "rr":
                    continue
                ev = by_key.get((label, i))
                if ev is None or not pred(ev):
                    continue
                if ev["addr"] is None:
                    continue
                pat = load_pattern(ev["addr"])
                n = len(pat)
                start = i - n + 1
                if start >= 0 and toks[start:i + 1] == pat:
                    drop.setdefault(label, set()).update(range(start, i + 1))
                    hits += 1
                else:
                    misses += 1
        return drop, hits, misses

    base_w, base_h = measure(flow)
    print("baseline controller: %dx%d  (box %d)" % (base_w, base_h, max(base_w, base_h) ** 2))

    scenarios = [
        ("drop REGISTER_RESIDENT+REDUNDANT",
         lambda e: e["cat"] in ("REGISTER_RESIDENT", "REDUNDANT")),
        ("drop ALL avoidable (needs a register file)",
         lambda e: e["cat"] in removable_cats),
    ]
    for name, pred in scenarios:
        drop, hits, misses = ranges_for(pred)
        stripped = strip(flow, drop)
        w, h = measure(stripped)
        n_ops = sum(1 for toks in stripped.blocks.values()
                    for t in toks if not isinstance(t, tuple))
        print("%-45s removed %3d loads (%d unmatched) -> %dx%d  box %d  ops %d"
              % (name, hits, misses, w, h, max(w, h) ** 2, n_ops))

    # --- absolute floor: strip EVERY port op and every non-terminator op ---
    empty = flowgrid.Flow()
    for label, toks in flow.blocks.items():
        empty.blocks[label] = [t for t in toks if isinstance(t, tuple)]
    w, h = measure(empty)
    nbr = sum(1 for toks in flow.blocks.values()
              if toks and isinstance(toks[-1], tuple) and toks[-1][0] == "br")
    ngo = sum(1 for toks in flow.blocks.values()
              if toks and isinstance(toks[-1], tuple) and toks[-1][0] == "go")
    print("\nCFG-SHAPE FLOOR (all ops deleted, CFG kept): %dx%d  box %d"
          % (w, h, max(w, h) ** 2))
    print("  blocks %d  br %d  go %d  -> blocks + 3*br + go = %d"
          % (len(flow.blocks), nbr, ngo, len(flow.blocks) + 3 * nbr + ngo))


if __name__ == "__main__":
    main()
