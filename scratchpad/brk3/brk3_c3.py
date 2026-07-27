#!/usr/bin/env python3
"""C at interior 12x3 is a MECHANICAL row deletion, not a re-lay.

Read off brk4's C_spec.json: rows 0, 2 and 3 carry 28 of the 29 cells, and row 1
carries exactly one -- `}` at (9,1).  So the 4-row interior is three working rows
plus a connector row that exists only to hold that one op.

Delete row 1.  Every vertical transition between old rows 0 and 2 ran THROUGH
row 1 as blank (only column 9 was occupied), so making them adjacent preserves
the walk exactly and costs a tick rather than adding one.  The single `}` is the
only thing that has to move, and the two extra columns 12x3 gives over 10x4 are
where it goes.

Placement: the man reaches `}` by leaving the branch `x` northward onto the turn
`<`, then running west along the top row.  Widening lets that run start two
columns further east, so `}` sits between the turn and `N`:

    old   (9,0)'<'  (9,1)'}'  (9,2)'x'          x -> north -> } -> < -> west
    new  (11,0)'<' (10,0)'}' (11,1)'x'          x -> north -> < -> west -> }

Same op order on the same walk, one row shorter.

  python3 brk3_c3.py [path/to/C_spec.json]
"""
import json
import os
import sys

SPEC = sys.argv[1] if len(sys.argv) > 1 else \
    "/Users/visenbaev/icfpc26/scratchpad/brk4/C_spec.json"
spec = json.load(open(SPEC))
old = {tuple(int(v) for v in k.split(",")): g for k, g in spec["cells"].items()}

row1 = {c: g for c, g in old.items() if c[1] == 1}
print(f"old interior {spec['interior']['w']}x{spec['interior']['h']}, "
      f"{len(old)} cells; row 1 holds {len(row1)}: "
      + ", ".join(f"{g!r}@{c}" for c, g in row1.items()))
assert len(row1) == 1, "row 1 is not a bare connector -- deletion is not mechanical"

SHIFT = 2                     # 12 wide vs 10: the two new columns go on the east
new = {}
for (x, y), g in old.items():
    if y == 1:
        continue
    ny = y - 1 if y >= 2 else y
    nx = x + SHIFT if x == 9 else x
    new[(nx, ny)] = g
(bx, by), bg = next(iter(row1.items()))
new[(bx + SHIFT - 1, 0)] = bg          # `}` onto the top row's westward run

W, H = 12, 3
print(f"\nnew interior {W}x{H}, {len(new)} cells "
      f"({len(new) / (W * H):.0%} fill):")
for y in range(H):
    print("  " + "".join(new.get((x, y), ".") for x in range(W)))

print("""
STILL TO CHECK before this is a build -- the hazard brk4 flagged:
C has SEVEN pipe ops against THREE wall attachments, and sends bind to the
nearest OUTGOING pipe while q/r/U bind to the nearest INCOMING one, so the two
groups are scored separately.  Old relative attachments were top (5,-1),
right (10,2), bottom (5,4); dropping a row and shifting column 9 east changes
every one of those distances.  Recompute per op and per direction, then place
the two `U`s last -- `U` turns AWAY from its supplying pipe, so its outgoing
direction is decided by the attachment it ends up bound to.""")
sends = [c for c, g in old.items() if g == "s"]
recvs = [c for c, g in old.items() if g in "qrU"]
print(f"  sends {sorted(sends)}\n  recvs {sorted(recvs)}")
