#!/usr/bin/env python3
"""Price candidate arrangements: box = max(w,h)^2, so trading width for height is
NEUTRAL once the two are equal.  Only total AREA reduction moves the box."""
rows = open('/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/'
            'solutions/sudoku-validity/lanes2.man').read().split('\n')
print("non-space cells:", sum(1 for r in rows for c in r if c != ' '), " box:", 48 * 46)

rooms = {'I': (3, 3), 'dispatch': (10, 6), 'ROW': (14, 11), 'COL': (14, 11),
         'BOX': (16, 12), 'gadget': (45, 15), 'AGG': (12, 7), 'O': (3, 3)}
tot = sum(w * h for w, h in rooms.values())
print("room bounding areas:", {k: w * h for k, (w, h) in rooms.items()})
print("sum of room areas:", tot, "-> smallest square that could hold them:",
      int(tot ** .5) + 1)

# The vertical stack is FORCED: the six mask pipes must enter the gadget's TOP
# wall (column-aligned) -- right-wall attachment binds every strip to the same
# pipe, since all six `r` cells share a row.
stack = dict(dispatch=5, addressing=12, gadget=15, agg=5, gaps=4 * 2)
print("forced vertical stack:", stack, "=", sum(stack.values()))

def price(name, band_w, band_h, gadget_h=15, agg_h=5, overhang=2):
    h = 5 + 2 + band_h + 2 + gadget_h + 2 + agg_h
    w = band_w + overhang
    print(f"{name:34s} w={w:3d} h={h:3d} box={max(w,h)**2:5d}")

print()
price("1 band, current rooms (14/14/16)", 46, 12)
price("1 band, narrow rooms (13/13/13)", 41, 18)
price("2 bands ROW|COL / BOX", 29, 11 + 2 + 12)
price("3 bands stacked", 16, 3 * 11 + 2 * 2)
print()
print("with timer (no AGG, gadget +2 for the timer ring):")
price("1 band + timer", 46, 12, gadget_h=17, agg_h=0)
price("1 band + timer + short strips", 46, 12, gadget_h=13, agg_h=0)
price("1 band + timer + per-room streams", 41, 16, gadget_h=17, agg_h=0, overhang=0)
