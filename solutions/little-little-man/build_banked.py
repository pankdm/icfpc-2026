#!/usr/bin/env python3
"""All-public LLM interpreter with separate scalar and cell RAM belts."""

import os

import build_multi as multi


HERE = os.path.dirname(__file__)
RAM_N = multi.PIPE_IO_RAM_N
SCALAR_RAM_N = RAM_N - (multi.DESC0 - 32)
CELL_RAM_N = 256
BANKED = True


def build_flow():
    return multi.build_flow(enable_io=True, banked=True)


def build():
    return multi.subset.build_program(
        build_flow(),
        SCALAR_RAM_N,
        display_addr=True,
        controller_code=380,
        port_profile="compact",
        pooled_edges=True,
        cell_ram_size=CELL_RAM_N,
    )


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "pipe-io-banked.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
