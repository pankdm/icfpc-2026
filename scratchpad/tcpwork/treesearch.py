#!/usr/bin/env python3
"""Minimum demux-clone latency over all legal 16-leaf decode trees.

The lap is pinned at 19 by parity (fork->r is Manhattan 6, so path lengths are
even; 12 loses the race, 14 is the shortest even win) and the race is decided by
the CLONE's latency. This enumerates decode trees and reports the minimum.

Model, all from measured semantics:
  * leaves occupy 16 distinct interior columns 1..16 (16 lane pipes, and the
    sweeper drains left-to-right, so leaf column must be MONOTONE in seq%16)
  * level i (1-indexed) tests bit 4-i of seq -- MSB first, forced by monotonicity
  * a node is entered heading SOUTH. Two node kinds:
      'x'  turns on BP bit0, ALWAYS deflects        -> children strictly either side
      'sd' straight-or-deflect (`&`+`X`, or `d`/`a`) -> one child same column
  * BP must equal seq>>(4-i) at level i. Right shifts only, so each level after
    the first needs a reload `b` plus (3-i) `]`. Those ride the glide between a
    node and its landing; whatever does not fit needs its own dedicated row.
  * 'sd' costs one extra row for its mask/reload (`&` or `b`); 'x' costs none.

Reports rows, horizontal moves and total clone latency for the best tree.
"""
import itertools, sys

NLEAF = 16
COLS = range(1, 17)


def prep_needed(level):
    """cells of BP prep required BEFORE level+1 (reload + shifts)."""
    return 1 + (3 - level) if level < 4 else 0


def build(kinds):
    """kinds: 4 node kinds. Returns (rows, horiz, latency) or None if illegal."""
    # groups[i] = list of (node_col, leaf_lo, leaf_hi) at level i
    groups = [[(None, 0, NLEAF - 1)]]
    total_h = 0
    extra_rows = 0
    layout = []
    for lvl in range(1, 5):
        kind = kinds[lvl - 1]
        span = NLEAF >> lvl            # leaves per child group
        newg = []
        lvl_h = 0
        need = prep_needed(lvl)
        worst_glide = None
        for (_, lo, hi) in groups[-1]:
            mid = lo + span
            # child column ranges are fixed bottom-up: leaf j sits at column j+1
            # so a group's node must reach both children's node columns.
            loC = lo + 1 + (span - 1) // 2 if lvl < 4 else lo + 1
            hiC = mid + 1 + (span - 1) // 2 if lvl < 4 else mid + 1
            if lvl == 4:
                loC, hiC = lo + 1, hi + 1
            if kind == 'sd':
                node = hiC if hiC - loC >= 0 else loC
                node = hiC          # straight child is the far one
                gl_lo = abs(node - loC) - 1
                gl_hi = 0
            else:
                node = (loC + hiC) // 2
                if node == loC or node == hiC:
                    return None      # 'x' must deflect BOTH ways
                gl_lo = abs(node - loC) - 1
                gl_hi = abs(node - hiC) - 1
            if gl_lo < 0 or gl_hi < 0:
                return None
            lvl_h = max(lvl_h, max(abs(node - loC), abs(node - hiC)))
            g = min(gl_lo, gl_hi)
            worst_glide = g if worst_glide is None else min(worst_glide, g)
            newg.append((node, lo, mid - 1))
            newg.append((node, mid, hi))
        # prep that does not fit in the glide needs dedicated rows
        if need > 0:
            short = max(0, need - (worst_glide if worst_glide is not None else 0))
            extra_rows += short
        total_h += lvl_h             # the clone walks ONE path: worst level cost
        groups.append(newg)
        layout.append((lvl, kind, need, worst_glide))
    rows = 4 + extra_rows
    # latency = vertical moves (== rows) + worst-case horizontal moves
    return rows, total_h, rows + total_h, layout


best = None
for kinds in itertools.product(['x', 'sd'], repeat=4):
    r = build(list(kinds))
    if r is None:
        continue
    rows, h, lat, layout = r
    if best is None or lat < best[0]:
        best = (lat, rows, h, kinds, layout)

print('kinds            rows  horiz  clone-latency')
for kinds in itertools.product(['x', 'sd'], repeat=4):
    r = build(list(kinds))
    if r is None:
        print(f'{"/".join(kinds):16s}  illegal')
        continue
    rows, h, lat, _ = r
    print(f'{"/".join(kinds):16s} {rows:5d} {h:6d} {lat:14d}')
print()
if best:
    print(f'BEST: {"/".join(best[3])}  rows={best[1]} horiz={best[2]} latency={best[0]}')
    print('  per level (lvl, kind, prep needed, glide available):')
    for row in best[4]:
        print('   ', row)
