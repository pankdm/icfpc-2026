#!/usr/bin/env python3
"""The honest count: measured upper bound vs lines actually evacuated, per champion."""
import os, subprocess, sys, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import place as P, evacuate as E

TARGETS = [
    ("matmul (given baseline, NOT live)", "solutions/matmul/live-9fb4b626.man"),
    ("matmul live 44x44 archive",         "submitted/matmul/9c4bf6c8-ab39-4f80-a0bd-ea61b2233f94.man"),
    ("gradebook LIVE",                    "solutions/gradebook/live-1bb8b72f.man"),
    ("snake LIVE",                        "solutions/snake/live-3887adaf.man"),
    ("subset-sum LIVE",                   "solutions/subset-sum/live-350d15b4.man"),
    ("pathfinder LIVE",                   "solutions/pathfinder/live-0138b404.man"),
    ("LLM LIVE",                          "solutions/little-little-man/ring-s5.man"),
    ("memory LIVE",                       "solutions/memory/live-7a52595b.man"),
    ("reverse-a-list LIVE",               "solutions/reverse-a-list/live-a0ee52e1.man"),
]

print(f"{'target':38s} {'dims':>9s} {'box':>9s} {'axis':>4s} "
      f"{'pipeonly':>8s} {'cand':>4s} {'shear':>5s} {'DONE':>4s} {'new box':>9s}")
for name, rel in TARGETS:
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        print(f"{name:38s}  MISSING {rel}"); continue
    try:
        plan = P.Plan(path)
    except SystemExit as e:
        print(f"{name:38s}  cannot plan: {e}"); continue
    x0, y0, x1, y1 = E.grid_bbox(plan.rows)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    ax = E.binding_axis(plan.rows)
    reps = E.scan_lines(plan, ax)
    cand = sum(1 for r in reps if r.verdict == "candidate")
    shear = sum(1 for r in reps if r.verdict == "shearable")
    text, log = E.evacuate_all(path, shear_modes=(0, -1, 1))
    nb = log[-1][4][2] if log else max(w, h) ** 2
    print(f"{name:38s} {w:4d}x{h:<4d} {max(w,h)**2:9,d} {ax:>4s} "
          f"{cand+shear:8d} {cand:4d} {shear:5d} {len(log):4d} {nb:9,d}")
