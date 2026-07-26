#!/usr/bin/env python3
"""LLM interpreter slice with parsed target-pipe topology.

The current checkpoint colors every target pipe and builds a compact descriptor
plus predecessor links for destination-to-source traversal. Pipe transport and
target ``s``/``r`` execution are added in subsequent increments.
"""
import os

import build_multi as multi


HERE = os.path.dirname(__file__)
RAM_N = multi.PIPE_RAM_N


def build_flow():
    return multi.build_flow(enable_pipes=True)


def build():
    return multi.subset.build_program(build_flow(), RAM_N, display_addr=True)


if __name__ == "__main__":
    program = build()
    output = os.path.join(HERE, "pipe-topology.man")
    program.save(output)
    print("saved", output, "footprint", program.footprint())
