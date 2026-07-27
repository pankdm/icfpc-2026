#!/usr/bin/env python3
"""Pathfinder bitset BFS v5 laid out with the dense rail CFG (tools/railflow.py).

Same flow as ``build_bitset6.build_reflow``; only the controller layout changes.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, HERE)

import railflow
import stateflow
import build_bitset6
from build_reflow_banked import alias_empty_gotos


def build(belts=9, scalar_belts=4, code_x=0, op_slack=0, verify=True,
          ports=None, floor=None, queue_rows=1, queue_right_off=300):
    flow = alias_empty_gotos(build_bitset6.build_flow())
    layout = {}

    def lay(program, graph, port_spec, code_x=code_x):
        if ports is not None:
            port_spec = ports
        forbid = set(range(code_x + 40, code_x + 70))
        forbid |= set(range(code_x + 156, code_x + 184))
        result = railflow.lay_cfg_rail(
            program, graph, port_spec, code_x=code_x, op_slack=op_slack,
            lit_forbid=forbid)
        layout.update(result)
        return result

    program = stateflow.build_program(
        flow,
        scalar_size=build_bitset6.SCALAR_RAM_N,
        scalar_belts=scalar_belts,
        fast_scalar_ram=True,
        scalar_command_band=2,
        scalar_reply_band=1,
        scalar_display_offset=60,
        code_x=code_x,
        queue=True,
        fast_cell_ram=True,
        cell_belts=belts,
        packed_cell=True,
        lay_fn=lay,
        queue_rows=queue_rows,
        queue_right_off=queue_right_off,
        floor=floor,
    )
    if verify:
        railflow.verify_bindings(program, layout)
    return program, layout


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--belts", type=int, default=9)
    ap.add_argument("--scalar-belts", type=int, default=4)
    ap.add_argument("--code-x", type=int, default=0)
    ap.add_argument("--op-slack", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    output = args.out or os.path.join(HERE, "rail-bitset5.man")
    program, layout = build(args.belts, args.scalar_belts, args.code_x,
                            args.op_slack, verify=not args.no_verify)
    program.save(output)
    print("saved", output, "footprint", program.footprint(),
          "controller", layout["width"], "x", layout["height"],
          "rail", layout["ncorr"])
