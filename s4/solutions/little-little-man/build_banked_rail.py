#!/usr/bin/env python3
"""LLM interpreter with the dense RAIL controller (tools/railflow.py).

Same program as ``build_banked_boustro.py``; only the CFG terminators change:
a jump costs 0 extra rows (the man is already westbound) and a branch 1 rail
row instead of boustro's 2 flattened rows.  Measured 876 -> 832 controller rows.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import railflow
import build_banked_dedup as dedup
import build_multi as multi
import echo_split
from build_banked_boustro import alias_empty_gotos


def build(code_x=45, op_slack=0, verify=True, hw_layout="tight", hw_gap=2,
          port_cols=None, nrail=10, extra_echoes=0):
    flow = alias_empty_gotos(dedup.build_flow())
    if extra_echoes:
        if not port_cols:
            raise SystemExit("--extra-echoes needs --port-cols")
        flow, _glyphs, est = echo_split.rewrite_flow(
            flow, port_cols, extra_echoes + 1, opmin=nrail + 2)
        print(f"echo split: {extra_echoes + 1} copies, est {est} code rows")
    layout = {}

    def lay(program, graph, port_spec, code_x=code_x):
        result = railflow.lay_cfg_rail(
            program,
            graph,
            port_spec,
            code_x=code_x,
            op_slack=op_slack,
            nrail=nrail,
        )
        layout.update(result)
        return result

    program = multi.subset.build_program(
        flow,
        dedup.SCALAR_RAM_N,
        display_addr=True,
        controller_code=code_x,
        port_profile="compact",
        pooled_edges=True,
        tight_gaps=True,
        dedup_edges=True,
        cell_ram_size=dedup.CELL_RAM_N,
        lay_fn=lay,
        hw_layout=hw_layout,
        hw_gap=hw_gap,
        port_cols=port_cols,
        extra_echoes=extra_echoes,
    )
    if verify:
        railflow.verify_bindings(program, layout)
    return program, layout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-x", type=int, default=45)
    parser.add_argument("--op-slack", type=int, default=0)
    parser.add_argument("--out")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--hw", choices=("wide", "tight"), default="tight")
    parser.add_argument("--hw-gap", type=int, default=2)
    parser.add_argument("--nrail", type=int, default=10)
    parser.add_argument("--extra-echoes", type=int, default=0)
    parser.add_argument("--port-cols", help="JSON dict of absolute port columns")
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    port_cols = json.loads(args.port_cols) if args.port_cols else None
    output = args.out or os.path.join(
        HERE, f"pipe-io-banked-dedup-rail{args.tag}.man")
    program, layout = build(
        args.code_x,
        args.op_slack,
        verify=not args.no_verify,
        hw_layout=args.hw,
        hw_gap=args.hw_gap,
        port_cols=port_cols,
        nrail=args.nrail,
        extra_echoes=args.extra_echoes,
    )
    if program.overwrites:
        print("OVERWRITES", program.overwrites[:5])
    program.save(output)
    print("saved", output, "footprint", program.footprint(),
          "controller", layout["width"], "x", layout["height"],
          "rails", layout["ncorr"])
