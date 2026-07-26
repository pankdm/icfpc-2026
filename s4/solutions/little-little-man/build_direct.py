#!/usr/bin/env python3
"""All-public LLM interpreter using direct target-local CFG routing."""

import os

import build_io


HERE = os.path.dirname(__file__)


def build():
    return build_io.multi.subset.build_program(
        build_io.build_flow(),
        build_io.RAM_N,
        display_addr=True,
        controller_code=340,
        port_profile="compact",
        direct_edges=True,
    )


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "pipe-io-direct.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
