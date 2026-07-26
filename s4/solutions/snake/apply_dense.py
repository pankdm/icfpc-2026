#!/usr/bin/env python3
"""Materialise a searched port/floor configuration into a named .man.

`search_rail.py` prints a `ports =` / `floor =` pair; this turns one into a grid
and runs the full trust chain before writing it, in this order, because each
stage catches something the previous one cannot see:

  1. build                 -- geometry that cannot even be laid out
  2. manlint.check         -- collisions, dangling pipe ends, stray literals
  3. railflow.verify_bindings -- every controller r/s binds the pipe it meant to
  4. one Rust public case  -- grids that load and then deadlock

Grade with tools/grade_fast.py afterwards; that is the number worth reporting.

  python3 solutions/snake/apply_dense.py --name dense-a \
      --ports '{"sp":1,...}' --floor '{"scalar_off":24,...}'
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, HERE)

import build_rail  # noqa: E402
import manlint  # noqa: E402
import railflow  # noqa: E402
import stateflow  # noqa: E402

SMOKE = "game over at the wall"


def materialise(name, ports, floor, slug="snake", smoke=SMOKE, lit=True,
                out_dir=HERE):
    spec = {n: (ports[n], stateflow.COMPACT_PORTS[n][1]) for n in ports}
    program, layout = build_rail.build(
        verify=False, ports=spec, floor=floor, lit=lit)
    w, h, box = program.footprint()
    print(f"{name}: {w}x{h} box {box:,} controller "
          f"{layout['width']}x{layout['height']} rail {layout['ncorr']}")
    fault = manlint.check(program)
    if fault:
        return f"lint: {fault}"
    railflow.verify_bindings(program, layout)
    path = os.path.join(out_dir, f"{name}.man")
    if os.path.exists(path):
        return f"{path} already exists -- never overwrite a working variant"
    program.save(path)
    got = subprocess.run(
        ["node", os.path.join(FORK, "sim", "rust_case.js"), slug, path, smoke],
        capture_output=True, text=True, cwd=FORK)
    if '"status":"pass"' not in got.stdout:
        os.unlink(path)
        return f"smoke case failed: {got.stdout.strip()[:200]}"
    print("wrote", path)
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--ports", required=True)
    ap.add_argument("--floor", required=True)
    ap.add_argument("--no-lit", action="store_true")
    args = ap.parse_args()
    problem = materialise(args.name, json.loads(args.ports),
                          json.loads(args.floor), lit=not args.no_lit)
    if problem:
        sys.exit(problem)
