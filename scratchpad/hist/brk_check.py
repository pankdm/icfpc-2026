#!/usr/bin/env python3
"""Independent check of the brk6 triple: place all five rooms on a real 16x16
grid, verify disjointness, interiors, and that pipe cells still have somewhere
to go.  Prints counts only."""
BOX = 16
def cells(x,y,w,h): return {(a,b) for a in range(x,x+w) for b in range(y,y+h)}

# headline triple from brk6_pack.py
rooms = {"M":(0,0,10,11), "P":(10,0,6,8), "C":(0,11,14,5)}
io    = {"I":(10,8,3,3), "O":(13,8,3,3)}
grid  = cells(0,0,BOX,BOX)
occ, bad = {}, []
for n,(x,y,w,h) in list(rooms.items())+list(io.items()):
    c = cells(x,y,w,h)
    if not c <= grid: bad.append((n,"outside box"))
    for p in c:
        if p in occ: bad.append((n,"overlaps "+occ[p],p))
        occ[p]=n
print("rooms placed:", {n:(w,h) for n,(x,y,w,h) in list(rooms.items())+list(io.items())})
print("overlap/out-of-box problems:", bad[:5] or "NONE")
print("cells used by rooms:", len(occ), "of", BOX*BOX, "-> free:", BOX*BOX-len(occ))
need = {"M":57,"P":21,"C":29}
for n,(x,y,w,h) in rooms.items():
    iw,ih=w-2,h-2
    print(f"  {n} outer {w}x{h} interior {iw}x{ih}={iw*ih} need {need[n]} "
          f"fill {need[n]/(iw*ih):.0%} {'OK' if need[n]<=iw*ih else 'OVERFLOW'}")
free = grid - set(occ)
print("free cells:", len(free), sorted(free)[:20])
