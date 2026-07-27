#!/usr/bin/env python3
"""region.py <man> <x0> <x1> <y0> <y1> — print a sub-rectangle with a column ruler."""
import sys, os
REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

rows = wf.load_rows(sys.argv[1])
x0, x1, y0, y1 = (int(a) for a in sys.argv[2:6])
print("     " + "".join(str(x // 10) if x % 10 == 0 else " " for x in range(x0, x1 + 1)))
print("     " + "".join(str(x % 10) for x in range(x0, x1 + 1)))
for y in range(y0, min(y1 + 1, len(rows))):
    r = rows[y].ljust(x1 + 1)
    print(f"{y:4d} " + r[x0:x1 + 1].replace(" ", "."))
