import sys, os
sys.path.insert(0,"solutions/matmul")
sys.path.insert(0,"tools")
import build_opt2 as B
b=B.build(stage="run")
p=b.p
minx=min(x for x,y in p.cells); maxx=max(x for x,y in p.cells)
miny=min(y for x,y in p.cells); maxy=max(y for x,y in p.cells)
print("builder bounds x",minx,maxx,"y",miny,maxy,"W",maxx-minx+1,"H",maxy-miny+1)
# For each column, list the min/max row that has a non-space pipe/wall glyph ABOVE ctrl (y<0)
print("\ncol: rows-above-ctrl (y<0) glyph counts")
for x in range(minx,maxx+1):
    ys=[y for (xx,y),c in p.cells.items() if xx==x and y<0 and c!=' ']
    if ys:
        print(f" col {x:3d}: y {min(ys):4d}..{max(ys):4d}  n={len(ys)}")
