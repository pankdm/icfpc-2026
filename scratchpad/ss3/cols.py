import sys
from collections import Counter
f=sys.argv[1]
rows=open(f).read().rstrip("\n").split("\n")
W=max(len(r) for r in rows)
print("grid %dx%d" % (W, len(rows)))
occ=[]
for x in range(W):
    ys=[y for y,r in enumerate(rows) if len(r)>x and r[x]!=" "]
    occ.append(ys)
for x in range(W-1, max(0,W-16), -1):
    ys=occ[x]
    ch=Counter(rows[y][x] for y in ys)
    print("col %2d  n=%3d rows=%s  %s" % (x, len(ys), (str(ys[:6])+".." if len(ys)>6 else str(ys)), dict(ch.most_common(5))))
print("--- rows (bottom/top)")
for y in list(range(0,3))+list(range(len(rows)-4,len(rows))):
    r=rows[y] if y < len(rows) else ""
    xs=[x for x,c in enumerate(r) if c!=" "]
    print("row %2d n=%3d span=%s" % (y, len(xs), (xs[0],xs[-1]) if xs else None))
