#!/usr/bin/env python3
"""Report which build_chainfield pipe overwrites an already-placed cell."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "solutions", "subset-sum"))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman
import build_chainfield as B

orig_put = littleman.Program.put
state = {"tag": "init"}


def put(self, x, y, ch):
    prev = self.cells.get((x, y))
    if prev is not None and prev != ch and prev != " ":
        print(f"OVERWRITE at ({x},{y}): {prev!r} -> {ch!r}   during {state['tag']}")
    return orig_put(self, x, y, ch)


littleman.Program.put = put

orig_pipe = littleman.Program.pipe


def pipe(self, points, **kw):
    state["tag"] = f"pipe {points}"
    return orig_pipe(self, points, **kw)


littleman.Program.pipe = pipe

nv = int(sys.argv[1]) if len(sys.argv) > 1 else 6
pp = int(sys.argv[2]) if len(sys.argv) > 2 else 2
m = B.build(nv, pp)
print("footprint", m.p.footprint())
