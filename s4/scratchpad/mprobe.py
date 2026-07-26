#!/usr/bin/env python3
"""Probe the SMT model's feasible envelope: SAT/UNSAT per knob combo, one Plan load.

  python3 scratchpad/mprobe.py <man> M:fan:cap:gap:extra:deficit:free[:obj] ...
      e.g.  200:wall:40:1:8:24:1   (M<=200, fan-order wall, move-cap 40, gap 1,
                                    extra 8, deficit 24, pipe-len free)
"""
import argparse, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import smtplace as SP
import place as PLACE

ap = argparse.ArgumentParser()
ap.add_argument("man")
ap.add_argument("specs", nargs="+")
ap.add_argument("--timeout", type=float, default=60.0)
ap.add_argument("--deltas", action="store_true")
a = ap.parse_args()

plan = SP.GroupPlan(a.man)
plan.route_guard = True
cells = plan.draw(plan.base_offsets, plan.pipe_paths_original())
bw, bh, bbox = PLACE.box_of(cells)
print(f"baseline {bw}x{bh} box {bbox}  M={max(bw,bh)}", flush=True)
for spec in a.specs:
    f = spec.split(":")
    m = int(f[0]); fan = f[1] if len(f) > 1 else "wall"
    cap = int(f[2]) if len(f) > 2 else 40
    gap = int(f[3]) if len(f) > 3 else 1
    extra = int(f[4]) if len(f) > 4 else 8
    deficit = int(f[5]) if len(f) > 5 else 24
    free = bool(int(f[6])) if len(f) > 6 else True
    obj = f[7] if len(f) > 7 else "none"
    mdl = SP.Model(plan, [], gap, extra, max(bw, bh), False, deficit=deficit,
                   parity=False, fan_order=fan, move_cap=cap, objectives=obj,
                   max_m=m, free_len=free)
    st, off, mv, dt = mdl.solve(a.timeout)
    print(f"  M<={m:4d} fan={fan:4s} cap={cap:3d} gap={gap} extra={extra:3d} "
          f"def={deficit:3d} free={int(free)} obj={obj:4s}: {st} ({dt:.1f}s)", flush=True)
    if off and a.deltas:
        moved = [(i, off[i][0] - plan.blocks[i].ox0, off[i][1] - plan.blocks[i].oy0)
                 for i in range(len(plan.blocks))
                 if off[i] != (plan.blocks[i].ox0, plan.blocks[i].oy0)]
        print(f"      deltas: {moved}", flush=True)
