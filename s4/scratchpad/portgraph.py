#!/usr/bin/env python3
"""Dump the room/pipe port geometry of a .man: which wall each pipe attaches to,
port coordinates per block, and the fan order per block pair."""
import sys, os
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import smtplace as SP   # noqa  (patches lift.analyze to the file-based one)
import place as PLACE

man = sys.argv[1]
plan = PLACE.Plan(man)
print(f"{len(plan.blocks)} blocks, {len(plan.pipes)} pipes, {len(plan.orphans)} orphans")
for bi, b in enumerate(plan.blocks):
    print(f"  block {bi:3d} {b.kind:7s} {b.w:4d}x{b.h:4d} at ({b.ox0},{b.oy0})")


def wall(b, off):
    ws = []
    if off[1] == 0: ws.append("T")
    if off[1] == b.h - 1: ws.append("B")
    if off[0] == 0: ws.append("L")
    if off[0] == b.w - 1: ws.append("R")
    return "".join(ws) or "?"


deg = {}
for p in plan.pipes:
    deg[p.src_b] = deg.get(p.src_b, 0) + 1
    deg[p.dst_b] = deg.get(p.dst_b, 0) + 1
print("degrees:", sorted(deg.items(), key=lambda kv: -kv[1]))

print("\npipes (idx: src_block[wall]off abs -> dst_block[wall]off abs, len):")
for p in plan.pipes:
    sb, db = plan.blocks[p.src_b], plan.blocks[p.dst_b]
    sa = (sb.ox0 + p.src_off[0], sb.oy0 + p.src_off[1])
    da = (db.ox0 + p.dst_off[0], db.oy0 + p.dst_off[1])
    print(f"  {p.idx:3d}: {p.src_b:3d}[{wall(sb,p.src_off)}]{p.src_off} {sa} -> "
          f"{p.dst_b:3d}[{wall(db,p.dst_off)}]{p.dst_off} {da}  L={p.length}")
