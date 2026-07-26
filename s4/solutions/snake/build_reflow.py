#!/usr/bin/env python3
"""Build Snake with compact services and a boustrophedon controller."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import boustro
import stateflow
import build as snake


def alias_empty_gotos(flow):
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


def build(code_x=10, op_slack=0, verify=True):
    flow = alias_empty_gotos(snake.build_flow())
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
        scalar_size=snake.SCALAR_RAM_N,
        code_x=code_x,
        compact=True,
        fast_cell_ram=True,
        cell_belts=8,
        fast_scalar_ram=True,
        scalar_belts=4,
        lay_fn=lay,
    )
    if verify:
        boustro.verify_bindings(program, layout)
    return program, layout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-x", type=int, default=10)
    parser.add_argument("--op-slack", type=int, default=0)
    parser.add_argument("--out")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    output = args.out or os.path.join(
        HERE,
        f"linked-compact-reflow-cx{args.code_x}-o{args.op_slack}.man",
    )
    program, layout = build(
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
