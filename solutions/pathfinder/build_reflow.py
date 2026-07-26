#!/usr/bin/env python3
"""Pathfinder reverse-bfs-fifo with the controller re-laid as a boustrophedon.

Same Flow, same ports, same hardware assembly (stateflow.build_program with
lay_fn=boustro.lay_cfg_boustrophedon), so every pipe keeps its exact
(src,dst,len) — including the 379-cell queue FIFO and the belt loops. Only the
controller geometry changes: dense band-constrained boustrophedon instead of
one-way east rows behind a 380-column corridor field.

The builder re-verifies every emitted r/s against the reference nearest-pipe
rule (attachment recovered from the rendered grid via the oracle) and refuses
to save on any mismatch.
"""

import os
import sys
import argparse
import functools

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import boustro
import stateflow
import build_fifo


def alias_empty_gotos(flow):
    """Drop op-less goto blocks; retarget every edge through them."""
    labels = list(flow.blocks)
    direct = {}
    for label in labels:
        toks = flow.blocks[label]
        ops = [t for t in toks if not isinstance(t, tuple)]
        if not ops and toks and isinstance(toks[-1], tuple) and toks[-1][0] == "go":
            direct[label] = toks[-1][1]

    def resolve(label):
        seen = set()
        while label in direct and label not in seen:
            seen.add(label)
            label = direct[label]
        return label

    for label in labels:
        toks = flow.blocks[label]
        if toks and isinstance(toks[-1], tuple):
            term = toks[-1]
            toks[-1] = (term[0],) + tuple(resolve(t) for t in term[1:])
    for label in direct:
        del flow.blocks[label]
    return flow


def verify_bindings(program, layout):
    """Every emitted r/s must bind the pipe attached at its intended port."""
    import pipecheck
    text = program.render()
    rows = text.split("\n")
    w = max(len(r) for r in rows)
    rows = [r.ljust(w) for r in rows]
    minx, miny, _, _ = program.bounds()
    topo = pipecheck.analyze(rows)
    if topo.get("type") == "error":
        raise SystemExit(f"analyze error: {topo.get('message')}")
    inc, out = pipecheck.attachments(topo)
    # controller is room 0 (topmost)
    att_pos = {}
    for pi, p in enumerate(topo["pipes"]):
        path = p.get("path") or []
        if not path:
            continue
        if p.get("src") == 0:
            att_pos[("out", pi)] = tuple(path[0]["pos"])
        if p.get("dst") == 0:
            att_pos[("in", pi)] = tuple(path[-1]["pos"])
    ports = layout["ports"]
    intent = layout["intent"]
    bad = []
    for (x, y), port in intent.items():
        gx, gy = x - minx, y - miny            # render() shifts to bounds
        ch = rows[gy][gx]
        kind = "out" if ch == "s" else "in"
        cands = (out if kind == "out" else inc).get(0, [])
        got = pipecheck.bind((gx, gy), cands)
        want_col = ports[port][0] - minx
        got_pos = att_pos.get((kind, got))
        if got_pos is None or got_pos[0] != want_col:
            bad.append(((x, y), port, got, got_pos, want_col))
    if bad:
        for b in bad[:10]:
            print("BAD BINDING:", b)
        raise SystemExit(f"{len(bad)} ops bind the wrong pipe")
    print(f"bindings OK: {len(intent)} port ops verified against the oracle")


def build(belts=9, code_x=30, op_slack=6, verify=True):
    flow = alias_empty_gotos(build_fifo.build_flow())
    holder = {}

    def lay(p, fl, port_spec, code_x=code_x):
        layout = boustro.lay_cfg_boustrophedon(
            p, fl, port_spec, code_x=code_x, op_slack=op_slack)
        holder.update(layout)
        return layout

    program = stateflow.build_program(
        flow,
        scalar_size=build_fifo.SCALAR_RAM_N,
        queue=True,
        fast_cell_ram=True,
        cell_belts=belts,
        packed_cell=True,
        code_x=code_x,
        lay_fn=lay,
    )
    if verify:
        verify_bindings(program, holder)
    return program, holder


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--belts", type=int, default=9)
    ap.add_argument("--code-x", type=int, default=30)
    ap.add_argument("--op-slack", type=int, default=6)
    ap.add_argument("--out", default=os.path.join(HERE, "reverse-bfs-reflow-b9.man"))
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    program, layout = build(args.belts, args.code_x, args.op_slack,
                            verify=not args.no_verify)
    program.save(args.out)
    print("saved", args.out, "footprint", program.footprint(),
          "controller", layout["width"], "x", layout["height"],
          "corridors", layout["ncorr"])
