#!/usr/bin/env python3
"""Re-price AFTER lanes4. The driver has flipped to HEIGHT (45), 0 empty rows/cols,
so a repack that only narrows the addressing rooms buys almost nothing: it attacks
a dimension that is no longer binding.

Height is a forced stack, because the six mask pipes must enter the gadget's TOP
wall (all six strip `r` cells share a row, so side attachment binds them all to
one pipe):
    dispatch 6 + gap 2 + band H + gap 2 + gadget 16 + gap 2 + O 3
"""
rows = open('/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/'
            'solutions/sudoku-validity/lanes4.man').read().split('\n')
print("lanes4 non-space cells:", sum(1 for r in rows for c in r if c != ' '), "box 2025")

now = {'ROW': (13, 13), 'COL': (13, 13), 'BOX': (15, 14)}
print("addressing room areas now:", {k: w * h for k, (w, h) in now.items()},
      "sum", sum(w * h for w, h in now.values()))

def price(name, band_w, band_h, gadget_h=16, disp_beside=False):
    h = (2 if disp_beside else 6 + 2) + band_h + 2 + gadget_h + 2 + 3
    w = 2 + band_w + (11 if disp_beside else 0)
    print(f"{name:46s} w={w:3d} h={h:3d} box={max(w,h)**2:5d}")

price("lanes4 (shipped)", 43, 14)
price("repack rooms only (7/7/9 wide, 12 tall)", 25, 12)
price("repack + dispatch beside band", 25, 12, disp_beside=True)
price("repack + dispatch beside + 7-row strips", 25, 12, gadget_h=13, disp_beside=True)
print("""
Verdict: narrowing the rooms alone is 43x43 -> 1849, a 9% box win for a full
rebuild of three rooms' fold + every pipe binding. The repack only pays once it
is combined with the two HEIGHT moves (dispatch beside the band, shorter strips),
and even then it is ~1296, not the ~784-900 estimated from the width figure.""")
