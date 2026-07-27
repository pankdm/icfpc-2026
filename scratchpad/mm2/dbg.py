#!/usr/bin/env python3
"""Print what occupies a window of the mm2 canvas, in absolute coordinates."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'solutions', 'matmul'))
import build_mm2 as B

g = None
try:
    g, a, b = B.build()
except Exception as e:
    print('build failed:', e, file=sys.stderr)
    import mm2lib
    g = getattr(B, '_last_grid', None)

if g is None:
    sys.exit(1)
x0, y0, x1, y1 = (int(v) for v in sys.argv[1:5])
print('    ' + ''.join(str(x % 10) for x in range(x0, x1 + 1)))
for y in range(y0, y1 + 1):
    print(f"{y:3d} " + ''.join(g.get(x, y).replace('\x02', '#').replace('\x01','~') for x in range(x0, x1 + 1)))
