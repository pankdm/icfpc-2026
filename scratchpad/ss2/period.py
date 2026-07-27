"""Find 4-row windows [r,r+4) where rows r..r+3 are identical to rows r+4..r+7 --
those are safe to delete (one whole replica) without changing anything else."""
import sys
MAN=sys.argv[1] if len(sys.argv)>1 else "scratchpad/ss2/teammate.man"
g=[l.rstrip("\n").rstrip() for l in open(MAN).read().split("\n")]
while g and not g[-1].strip(): g.pop()
ok=[]
for r in range(0,len(g)-8):
    if all(g[r+i]==g[r+4+i] for i in range(4)): ok.append(r)
print("H=%d  safe delete windows (row r, deletes r..r+3): %s"%(len(g),ok))
