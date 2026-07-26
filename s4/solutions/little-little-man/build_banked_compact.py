#!/usr/bin/env python3
"""Banked full solver with minimum safe CFG merge/branch gaps."""

import os

import build_banked
import build_multi as multi


HERE = os.path.dirname(__file__)
RAM_N = build_banked.RAM_N
SCALAR_RAM_N = build_banked.SCALAR_RAM_N
CELL_RAM_N = build_banked.CELL_RAM_N
BANKED = True


def build_flow():
    return build_banked.build_flow()


def build():
    return multi.subset.build_program(
        build_flow(),
        SCALAR_RAM_N,
        display_addr=True,
        controller_code=380,
        port_profile="compact",
        pooled_edges=True,
        tight_gaps=True,
        cell_ram_size=CELL_RAM_N,
    )


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "pipe-io-banked-compact.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
