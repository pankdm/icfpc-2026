import sys
MAN=sys.argv[1] if len(sys.argv)>1 else "scratchpad/ss2/teammate.man"
g=[l.rstrip("\n") for l in open(MAN).read().split("\n")]
while g and not g[-1].strip(): g.pop()
W=max(len(l) for l in g); H=len(g)
def at(x,y): return g[y][x] if 0<=y<H and 0<=x<len(g[y]) else " "
for x in range(70,W):
    rows=[y for y in range(H) if at(x,y)!=" "]
    print("col %2d: %3d used  rows %s%s"%(x,len(rows),rows[:14],"..." if len(rows)>14 else ""))
