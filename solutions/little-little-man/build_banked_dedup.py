#!/usr/bin/env python3
"""Compact banked solver with coalesced equal-target branch arms."""

import os

import build_banked_compact as compact
import build_multi as multi


HERE = os.path.dirname(__file__)
RAM_N = compact.RAM_N
SCALAR_RAM_N = compact.SCALAR_RAM_N
CELL_RAM_N = compact.CELL_RAM_N
BANKED = True


def build_flow():
    return compact.build_flow()


def build():
    return multi.subset.build_program(
        build_flow(),
        SCALAR_RAM_N,
        display_addr=True,
        controller_code=380,
        port_profile="compact",
        pooled_edges=True,
        tight_gaps=True,
        dedup_edges=True,
        cell_ram_size=CELL_RAM_N,
    )


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "pipe-io-banked-dedup.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
