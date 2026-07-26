#!/usr/bin/env python3
"""Build the scalar-banked Pathfinder with a boustrophedon controller."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import boustro
import stateflow
import build_fifo


def alias_empty_gotos(flow):
    """Remove operation-free goto aliases before physical layout."""
    direct = {}
    for label, tokens in flow.blocks.items():
        ops = [token for token in tokens if not isinstance(token, tuple)]
        if (
            not ops
            and tokens
            and isinstance(tokens[-1], tuple)
            and tokens[-1][0] == "go"
        ):
            direct[label] = tokens[-1][1]

    def resolve(label):
        seen = set()
        while label in direct and label not in seen:
            seen.add(label)
            label = direct[label]
        return label

    for tokens in flow.blocks.values():
        if tokens and isinstance(tokens[-1], tuple):
            term = tokens[-1]
            tokens[-1] = (term[0],) + tuple(resolve(t) for t in term[1:])
    for label in direct:
        del flow.blocks[label]
    return flow


def build(belts=9, scalar_belts=4, code_x=0, op_slack=0, verify=True):
    flow = alias_empty_gotos(build_fifo.build_flow())
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
        scalar_size=build_fifo.SCALAR_RAM_N,
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
        "reverse-bfs-fifo-b9-s"
        f"{args.scalar_belts}-reflow-cx{args.code_x}-o{args.op_slack}.man",
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
        "saved",
        output,
        "footprint",
        program.footprint(),
        "controller",
        layout["width"],
        "x",
        layout["height"],
        "corridors",
        layout["ncorr"],
    )
