import sys
sys.path.insert(0,"solutions/matmul"); sys.path.insert(0,"tools")
import build_opt2 as B
b=B.build(stage="run"); p=b.p
# CTRL rows used (y>=0) — which rows have non-wall content
minx=min(x for x,y in p.cells); maxx=max(x for x,y in p.cells)
maxy=max(y for x,y in p.cells)
print("CTRL bottom wall y=", maxy)
blank=[]
used=[]
for y in range(1,maxy):
    cells=[(x,c) for (x,yy),c in p.cells.items() if yy==y and c not in (' ',)]
    # is this a CTRL-interior blank row (only '|' walls)?
    nonwall=[c for x,c in cells if c!='|']
    if not nonwall:
        blank.append(y)
    else:
        used.append(y)
print("CTRL interior rows total:", maxy-1)
print("blank (compactable) rows:", len(blank), blank)
print("used rows:", len(used), "span", min(used),"..",max(used))
