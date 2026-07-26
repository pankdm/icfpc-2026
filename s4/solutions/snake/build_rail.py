#!/usr/bin/env python3
"""Snake with the dense rail-routed CFG controller (tools/railflow.py)."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import railflow
import stateflow
import build as snake
from build_reflow import alias_empty_gotos


def build(code_x=10, op_slack=0, verify=True, ports=None, floor=None):
    flow = alias_empty_gotos(snake.build_flow())
    layout = {}

    def lay(program, graph, port_spec, code_x=code_x):
        if ports is not None:
            port_spec = ports
        result = railflow.lay_cfg_rail(
            program, graph, port_spec, code_x=code_x, op_slack=op_slack)
        layout.update(result)
        return result

    program = stateflow.build_program(
        flow,
        scalar_size=snake.SCALAR_RAM_N,
        code_x=code_x,
        compact=True,
        fast_cell_ram=True,
        cell_belts=8,
        fast_scalar_ram=True,
        scalar_belts=4,
        lay_fn=lay,
        floor=floor,
    )
    if verify:
        railflow.verify_bindings(program, layout)
    return program, layout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-x", type=int, default=10)
    parser.add_argument("--op-slack", type=int, default=0)
    parser.add_argument("--out")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    output = args.out or os.path.join(
        HERE, f"rail-cx{args.code_x}-o{args.op_slack}.man")
    program, layout = build(args.code_x, args.op_slack,
                            verify=not args.no_verify)
    program.save(output)
    print("saved", output, "footprint", program.footprint(),
          "controller", layout["width"], "x", layout["height"],
          "rail", layout["ncorr"])
