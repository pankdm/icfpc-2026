import sys, json
sys.path.insert(0,'tools'); sys.path.insert(0,'tools')
sys.setrecursionlimit(100000)
import place as P, exact_pipe_router as R

SRC = sys.argv[1] if len(sys.argv)>1 else '/tmp/mm-live.man'
NEW8 = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv)>3 else (20,36)

pl = P.Plan(SRC)
off = [list(o) for o in pl.base_layout()[0]]
off[8] = list(NEW8)
b8 = pl.blocks[8]

# occupancy: all blocks at new offsets + every pipe except 8,10,11
occ = set()
for b,(ox,oy) in zip(pl.blocks, off):
    for x in range(ox, ox+b.w):
        for y in range(oy, oy+b.h): occ.add((x,y))
for j,p in enumerate(pl.pipes):
    if j in (8,10,11): continue
    occ.update(p.cells)

MAXY = 43                      # <-- the whole point: nothing may use row 44
free = {(x,y) for y in range(0,MAXY+1) for x in range(0,44) if (x,y) not in occ}
print("free cells (rows<=43):", len(free))

base_off = [list(o) for o in pl.base_layout()[0]]
def attach(bi, off_xy, use_base=False):
    ox,oy = (base_off if use_base else off)[bi]
    return (ox+off_xy[0], oy+off_xy[1])

specs = []
for j in (11,8,10):
    p = pl.pipes[j]
    s_att = attach(p.src_b, p.src_off)
    d_att = attach(p.dst_b, p.dst_off)
    s_old = attach(p.src_b, p.src_off, True)
    fd = (p.cells[0][0]-s_old[0], p.cells[0][1]-s_old[1])   # dir taken at the ORIGINAL attach
    ld = p.dirs[-1]
    start = (s_att[0]+fd[0], s_att[1]+fd[1])
    end   = (d_att[0]-ld[0], d_att[1]-ld[1])
    specs.append((j, start, fd, end, ld, p.length))
    print(f"pipe{j}: start {start} firstdir {fd} -> end {end} lastdir {ld} len {p.length}")

paths = {}
for (j, start, fd, end, ld, L) in specs:
    avail = set(free)
    for pj,pc in paths.items(): avail -= set(pc)
    got = None
    for seed in range(6):
        got = R.route_exact(avail, start, fd, end, ld, L, seed=seed,
                            budget=1500000 if L>100 else 300000)
        if got: break
    if not got:
        print(f"  pipe{j}: FAILED"); sys.exit(1)
    print(f"  pipe{j}: routed {len(got)} cells (need {L})")
    paths[j] = got

allpaths = pl.pipe_paths_original()
for j,cells in paths.items():
    ld = pl.pipes[j].dirs[-1]
    allpaths[j] = (cells, R.dirs_of(cells, ld))
cells = P.trimmed(pl.draw([tuple(o) for o in off], allpaths))
txt = P.render(cells)
open('/tmp/mmfold/out.man','w').write(txt)
w = max(len(l) for l in txt.split('\n')); h = len([l for l in txt.split('\n') if l.strip()])
print(f"RESULT {w}x{h} box {max(w,h)**2}")
