#!/usr/bin/env python3
"""Cell budget of a history-lesson grid: how many cells are literal payload,
how long are the literals, and how much information do they actually carry."""
import collections, math, re, sys

path = sys.argv[1] if len(sys.argv) > 1 else \
    "/Users/visenbaev/icfpc26/solutions/history-lesson/best/81x81.man"
rows = [r.rstrip() for r in open(path).read().split("\n")]
while rows and not rows[-1]:
    rows.pop()
w = max(len(r) for r in rows)
h = len(rows)
rows = [r.ljust(w) for r in rows]

c = collections.Counter()
for r in rows:
    for ch in r:
        c[ch] += 1

# horizontal literal runs: `digits`
lens, vals = [], []
for r in rows:
    for m in re.finditer(r"`([0-9 ]*)`", r):
        d = m.group(1).replace(" ", "")
        if d:
            lens.append(len(d))
            vals.append(int(d))

nonspace = sum(v for k, v in c.items() if k != " ")
dig = sum(v for k, v in c.items() if k.isdigit())
bt = c["`"]
bits = sum(max(1, v.bit_length()) for v in vals)
print(f"{w}x{h} box={max(w,h)**2} nonspace={nonspace} fill={nonspace/(w*h):.1%}")
print(f"digits={dig} backticks={bt} literal_cells={dig+bt} "
      f"({(dig+bt)/nonspace:.0%} of the ink)")
print(f"h-literals={len(lens)} len: min={min(lens)} med={sorted(lens)[len(lens)//2]} "
      f"max={max(lens)} mean={sum(lens)/len(lens):.1f}")
print("len histogram:", sorted(collections.Counter(lens).items()))
print(f"payload bits carried={bits} ({bits/8:.0f} B) over {dig} digit cells "
      f"= {bits/dig:.2f} bits/cell (ceiling 3.32)")
print(f"incl. backticks: {bits/(dig+bt):.2f} bits/cell")
print(f"target text 2810 B; ratio achieved {bits/8/2810:.3f}; gzip 1563 B = 0.556")
print("\nnon-literal ink by glyph:",
      sorted(((v, k) for k, v in c.items() if k != " " and not k.isdigit()
              and k != "`"), reverse=True)[:16])
