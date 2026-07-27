"""The replica band has period 4.  Compare every 4-row block against the modal
block and report any cell that differs -- a transcription typo cannot hide."""
import sys
from collections import Counter
MAN=sys.argv[1] if len(sys.argv)>1 else "scratchpad/ss2/teammate.man"
g=[l.rstrip("\n") for l in open(MAN).read().split("\n")]
while g and not g[-1].strip(): g.pop()
W=max(len(l) for l in g)
g=[l.ljust(W) for l in g]
# blocks aligned to the period: find the best phase over rows 10..86
best=None
for phase in range(4):
    blocks=[tuple(g[r:r+4]) for r in range(10+phase,86,4) if r+4<=len(g)]
    c=Counter(blocks)
    if not c: continue
    top,n=c.most_common(1)[0]
    if best is None or n>best[1]: best=(phase,n,top,blocks,10+phase)
phase,n,top,blocks,start=best
print("phase %d: %d blocks, modal appears %d times"%(phase,len(blocks),n))
for i,b in enumerate(blocks):
    if b==top: continue
    r0=start+4*i
    diffs=[]
    for j in range(4):
        a,bb=top[j],b[j]
        for x in range(max(len(a),len(bb))):
            ca=a[x] if x<len(a) else " "
            cb=bb[x] if x<len(bb) else " "
            if ca!=cb: diffs.append((r0+j,x,ca,cb))
    print("block rows %d..%d : %d diffs %s"%(r0,r0+3,len(diffs),diffs[:12]))
