#!/usr/bin/env python3
"""Snake with the dense rail-routed CFG controller (tools/railflow.py).

``--lit`` also replaces ``flowgrid.const_ops`` with atomic backtick literals.
That matters for more than op count: ``const_ops`` builds a value out of
``M``/``+``, which clobbers ``B``, which is the only reason
``stateflow.Flow.load``/``store`` route addresses >= 10 through the scratch FIFO
(``sp``/``rp``).  A literal loads ``A`` alone, so every load and store collapses
to the digit-address form -- and with it the ``cc -> rp -> cc`` band alternation
that was costing four boustrophedon rows per cell store.

  const_ops   1153 code cells, controller 139x165, box 47,524
  literals     864 code cells, controller 139x157, box 44,100
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import railflow
import stateflow
import build as snake
from build_reflow import alias_empty_gotos


def _lit_const(self, n):
    if 0 <= n < 10:
        return self.e(str(n))
    return self.e(f"`{n}`")


def _lit_load(self, addr):
    """A := scalar[addr], preserving B -- literal addresses need no scratch."""
    return self.const(0).e("sc").const(addr).e("sc", "rr")


def _lit_store(self, addr):
    return self.e("M").const(1).e("sc").const(addr).e("sc", "W", "sc")


def build(code_x=10, op_slack=0, verify=True, ports=None, floor=None, lit=True):
    saved = (snake.Flow.const, snake.Flow.load, snake.Flow.store)
    if lit:
        snake.Flow.const = _lit_const
        snake.Flow.load = _lit_load
        snake.Flow.store = _lit_store
    try:
        flow = alias_empty_gotos(snake.build_flow())
    finally:
        snake.Flow.const, snake.Flow.load, snake.Flow.store = saved
    layout = {}

    # Component init literals sit below the controller; a controller backtick in
    # the same COLUMN would pair with one of them into a vertical literal
    # spanning walls and pipes, which the loader rejects.
    f = floor or {}
    forbid = set()
    for off in (f.get("scalar_off", 24), f.get("cell_off", 112)):
        forbid |= set(range(code_x + off + 3, code_x + off + 17))

    def lay(program, graph, port_spec, code_x=code_x):
        if ports is not None:
            port_spec = ports
        result = railflow.lay_cfg_rail(
            program, graph, port_spec, code_x=code_x, op_slack=op_slack,
            lit_forbid=forbid if lit else ())
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
        floor=floor,
    )
    if verify:
        railflow.verify_bindings(program, layout)
    return program, layout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-x", type=int, default=10)
    parser.add_argument("--op-slack", type=int, default=0)
    parser.add_argument("--no-lit", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    output = args.out or os.path.join(
        HERE, f"rail-cx{args.code_x}-o{args.op_slack}"
              f"{'' if args.no_lit else '-lit'}.man")
    program, layout = build(args.code_x, args.op_slack,
                            verify=not args.no_verify, lit=not args.no_lit)
    program.save(output)
    print("saved", output, "footprint", program.footprint(),
          "controller", layout["width"], "x", layout["height"],
          "rail", layout["ncorr"])
