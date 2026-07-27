#!/usr/bin/env python3
"""Where do CTRL's fifo rotations go?  Rotations are pure tax: each is 2 cells in
CTRL and 2 more in BRAIN's echo loop."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                "solutions", "plotter"))
import swar_setup as S


class Spy(S.Emit):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rots = []
        self.passed = {}

    def fetch(self, name):
        n = 0
        while self.q[0][0] != name:
            self.passed[self.q[0][0]] = self.passed.get(self.q[0][0], 0) + 1
            self.rot()
            n += 1
        self.rots.append((name, n, len(self.q)))
        return super().fetch(name)


e = Spy(3, 4, 20, 19)
S.setup(e)
tot = sum(n for _, n, _ in e.rots)
print(f"ops {len(e.toks)}  pushes {e.npush}  fetches {len(e.rots)}  rotations {tot}")
print("\nrotations charged to the value that was IN THE WAY:")
for k, v in sorted(e.passed.items(), key=lambda kv: -kv[1]):
    print(f"  {k:7s} {v:4d}")
print("\nfetches that paid the most (name, rotations, fifo depth at the time):")
for name, n, d in sorted(e.rots, key=lambda r: -r[1])[:14]:
    print(f"  {name:7s} {n:3d}  depth {d}")
