#!/usr/bin/env python3
"""Build the banked/deduplicated LLM interpreter with a dense controller."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import boustro
import build_banked_dedup as dedup
import build_multi as multi


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


def build(code_x=45, op_slack=0, verify=True, hw_layout="wide", hw_gap=2,
          flat_branch=False):
    flow = alias_empty_gotos(dedup.build_flow())
    layout = {}

    def lay(program, graph, port_spec, code_x=code_x):
        result = boustro.lay_cfg_boustrophedon(
            program,
            graph,
            port_spec,
            code_x=code_x,
            op_slack=op_slack,
            flat_branch=flat_branch,
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
    )
    if verify:
        boustro.verify_bindings(program, layout)
    return program, layout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-x", type=int, default=45)
    parser.add_argument("--op-slack", type=int, default=0)
    parser.add_argument("--out")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--hw", choices=("wide", "tight"), default="wide")
    parser.add_argument("--hw-gap", type=int, default=2)
    parser.add_argument("--flat-branch", action="store_true")
    args = parser.parse_args()
    suffix = "" if args.hw == "wide" else f"-hw{args.hw_gap}"
    if args.flat_branch:
        suffix += "-fb"
    output = args.out or os.path.join(
        HERE,
        f"pipe-io-banked-dedup-boustro-cx{args.code_x}-o{args.op_slack}{suffix}.man",
    )
    program, layout = build(
        args.code_x,
        args.op_slack,
        verify=not args.no_verify,
        hw_layout=args.hw,
        hw_gap=args.hw_gap,
        flat_branch=args.flat_branch,
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
