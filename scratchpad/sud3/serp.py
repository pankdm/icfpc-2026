#!/usr/bin/env python3
"""Dense serpentine loop: fills a room's interior instead of only its perimeter.

A ring holds ops only on its boundary, so ROW/COL/BOX were spending 548 cells to
carry 90 ops (~16% density).  A boustrophedon that fills the rectangle and
returns up a single lane carries the same ops in a fraction of the area.

Interior is W x H with H ODD (so the last body row runs westward and can exit
into the return lane).  Layout, interior coords x=0..W-1, y=0..H-1:

    @ v . . . . . .        (0,0)='@' start, (1,0)='v' drops into the loop
    > > o o o o o v        (0,1)='>' return-lane turn, (1,1)='>' loop entry
    ^ v o o o o o <
    ^ > o o o o o v
    ^ o o o o o o <        last body row runs west and exits at (0,H-1)

Cycle: row 1 east, then alternate west/east, then up column 0 back to (0,1).
Capacity = (H-2)*(W-3) + (W-2).
"""

def serp(W, H):
    """Return (slots, glyphs, cycle) -- ordered op cells, fixed direction cells,
    and the tick index of every cell in the loop (so segment costs, including
    turn cells, can be priced exactly)."""
    assert H % 2 == 1 and H >= 3 and W >= 5, (W, H)
    g = {(0, 0): "@", (1, 0): "v", (0, 1): ">", (1, 1): ">"}
    for y in range(2, H):
        g[(0, y)] = "^"
    slots = []
    for y in range(1, H):
        if y == 1:
            xs, g[(W - 1, 1)] = range(2, W - 1), "v"
        elif y == H - 1:
            g[(W - 1, y)] = "<"
            xs = range(W - 2, 0, -1)          # runs on to x=1, then out to (0,y)
        elif y % 2 == 1:
            g[(1, y)] = ">"
            xs, g[(W - 1, y)] = range(2, W - 1), "v"
        else:
            g[(W - 1, y)] = "<"
            xs = range(W - 2, 1, -1)
            g[(1, y)] = "v"
        slots += [(x, y) for x in xs]

    # walk the cycle to price every cell in ticks
    cycle, pos, d = {}, (1, 1), (1, 0)
    for t in range(4 * W * H):
        if pos in cycle:
            break
        cycle[pos] = t
        ch = g.get(pos)
        if ch == ">": d = (1, 0)
        elif ch == "<": d = (-1, 0)
        elif ch == "v": d = (0, 1)
        elif ch == "^": d = (0, -1)
        pos = (pos[0] + d[0], pos[1] + d[1])
    return slots, g, cycle

def capacity(W, H):
    return (H - 2) * (W - 3) + (W - 2)

def place(p, x0, y0, W, H, ops):
    """Draw the loop at interior origin (x0,y0); return absolute op coordinates."""
    slots, g, _ = serp(W, H)
    assert len(ops) <= len(slots), (len(ops), len(slots))
    for (dx, dy), ch in g.items():
        p.put(x0 + dx, y0 + dy, ch)
    out = []
    for i, (dx, dy) in enumerate(slots):
        p.put(x0 + dx, y0 + dy, ops[i] if i < len(ops) else " ")
        out.append((x0 + dx, y0 + dy))
    return out

def segment(W, H, i, j):
    """Ticks from op i to op j along the loop, counting turn cells crossed."""
    slots, _, cycle = serp(W, H)
    return cycle[slots[j]] - cycle[slots[i]]

def loop_len(W, H):
    return len(serp(W, H)[2])
