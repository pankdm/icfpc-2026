#!/usr/bin/env python3
"""Boustrophedon-reflowed build of the bitset2 Pathfinder flow."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import boustro
import stateflow
import build_bitset2
from build_reflow_banked import alias_empty_gotos


def build(belts=9, scalar_belts=4, code_x=0, op_slack=0, verify=True):
    flow = alias_empty_gotos(build_bitset2.build_flow())
    layout = {}

    def lay(program, graph, port_spec, code_x=code_x):
        result = boustro.lay_cfg_boustrophedon(
            program,
            graph,
            port_spec,
            code_x=code_x,
            op_slack=op_slack,
        )
        layout.update(result)
        return result

    program = stateflow.build_program(
        flow,
        scalar_size=build_bitset2.SCALAR_RAM_N,
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
    )
    if verify:
        boustro.verify_bindings(program, layout)
    return program, layout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--belts", type=int, default=9)
    parser.add_argument("--scalar-belts", type=int, default=4)
    parser.add_argument("--code-x", type=int, default=0)
    parser.add_argument("--op-slack", type=int, default=0)
    parser.add_argument("--out")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    output = args.out or os.path.join(
        HERE,
        "reverse-bfs-bitset2-b"
        f"{args.belts}-s{args.scalar_belts}-reflow-cx{args.code_x}"
        f"-o{args.op_slack}.man",
    )
    program, layout = build(
        args.belts,
        args.scalar_belts,
        args.code_x,
        args.op_slack,
        verify=not args.no_verify,
    )
    program.save(output)
    print(
        "saved", output,
        "footprint", program.footprint(),
        "controller", layout["width"], "x", layout["height"],
        "corridors", layout["ncorr"],
    )
