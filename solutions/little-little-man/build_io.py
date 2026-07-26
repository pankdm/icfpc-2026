#!/usr/bin/env python3
"""LLM interpreter with multi-room scheduling and target pipe s/r semantics."""
import os

import build_multi as multi


HERE = os.path.dirname(__file__)
RAM_N = multi.PIPE_IO_RAM_N


def build_flow():
    return multi.build_flow(enable_io=True)


def build():
    return multi.subset.build_program(
        build_flow(),
        RAM_N,
        display_addr=True,
        controller_code=340,
        port_profile="compact",
        local_edges=True,
    )


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "pipe-io.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
