"""Re-route every pipe that leaves a target window, at EXACT original length."""
import sys
sys.path.insert(0,'tools'); sys.path.insert(0,'tools')
sys.setrecursionlimit(200000)
import place as P, exact_pipe_router as R

SRC=sys.argv[1]; X0,X1,Y0,Y1=map(int,sys.argv[2:6]); OUT=sys.argv[6]
MOVES=[m.split(':') for m in sys.argv[7:]]      # "blk:x:y"
pl=P.Plan(SRC)
off=[list(o) for o in pl.base_layout()[0]]
base=[list(o) for o in pl.base_layout()[0]]
for m in MOVES: off[int(m[0])]=[int(m[1]),int(m[2])]

for b,(ox,oy) in zip(pl.blocks,off):
    if not (X0<=ox and ox+b.w-1<=X1 and Y0<=oy and oy+b.h-1<=Y1):
        print(f"block{b.idx} at ({ox},{oy}) {b.w}x{b.h} is OUTSIDE window"); sys.exit(2)

newocc=set()
for b,(ox,oy) in zip(pl.blocks,off):
    for x in range(ox,ox+b.w):
        for y in range(oy,oy+b.h): newocc.add((x,y))
moved={int(m[0]) for m in MOVES}
bad=[p.idx for p in pl.pipes
     if any(not(X0<=x<=X1 and Y0<=y<=Y1) for x,y in p.cells)
     or any(c in newocc for c in p.cells)
     or p.src_b in moved or p.dst_b in moved]
print("window", (X0,X1,Y0,Y1), "-> re-route pipes", bad)

occ=set()
for b,(ox,oy) in zip(pl.blocks,off):
    for x in range(ox,ox+b.w):
        for y in range(oy,oy+b.h): occ.add((x,y))
for p in pl.pipes:
    if p.idx not in bad: occ.update(p.cells)
free={(x,y) for y in range(Y0,Y1+1) for x in range(X0,X1+1) if (x,y) not in occ}
print("free cells in window:", len(free), "| pipes to place:", sum(pl.pipes[i].length for i in bad))

specs=[]
for j in bad:
    p=pl.pipes[j]
    ox,oy=off[p.src_b]; s=(ox+p.src_off[0], oy+p.src_off[1])
    ox,oy=off[p.dst_b]; d=(ox+p.dst_off[0], oy+p.dst_off[1])
    bx,by=base[p.src_b]; so=(bx+p.src_off[0], by+p.src_off[1])
    fd=(p.cells[0][0]-so[0], p.cells[0][1]-so[1]); ld=p.dirs[-1]
    specs.append((j,(s[0]+fd[0],s[1]+fd[1]),fd,(d[0]-ld[0],d[1]-ld[1]),ld,p.length))
order=sorted(specs,key=lambda t:t[5])   # short, position-critical pipes first
paths={}
for (j,start,fd,end,ld,L) in order:
    avail=set(free)
    for pc in paths.values(): avail-=set(pc)
    got=None
    for seed in range(8):
        got=R.route_exact(avail,start,fd,end,ld,L,seed=seed,
                          budget=4000000 if L>100 else 500000)
        if got: break
    if not got: print(f"  pipe{j}: FAILED (len {L})"); sys.exit(1)
    print(f"  pipe{j}: routed {len(got)}/{L}"); paths[j]=got

allp=pl.pipe_paths_original()
for j,c in paths.items(): allp[j]=(c, R.dirs_of(c, pl.pipes[j].dirs[-1]))
txt=P.render(P.trimmed(pl.draw([tuple(o) for o in off], allp)))
open(OUT,'w').write(txt)
w=max(len(l) for l in txt.split('\n')); h=len([l for l in txt.split('\n') if l.strip()])
print(f"RESULT {w}x{h} box {max(w,h)**2}")
