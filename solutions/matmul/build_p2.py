#!/usr/bin/env python3
"""Matmul P2-CC — full machine. See docs/matmul-carousel-design.md (P2-CC).

CTRL (0,0,18,19), W (20,0,12,8), BRT retranslator (33,1,9,4).
Controller rows: 1-8 seeder, 9 boundary, 10 A-pop, 11 test, 12 real-lane,
13 descent, 14-15 steady loop, 16-17 emit loop. Riser col 1.
North attaches: AR@2 IN@4 BFS@6 MR@8 MF@10 KR@14 KF@15 AF@16.
South attaches (y=19): CIN@3 CRET@4 HA@5 OUTA@6.
"""
import os, sys
REPO = os.path.abspath(__file__).split("/solutions/")[0]
sys.path.insert(0, REPO + "/tools")
import littleman as lm

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

class B:
    def __init__(self):
        self.p = lm.Program(); self.placed = {}; self.intent = {}
    def C(self, x, y, ch, bind=None):
        if (x, y) in self.placed and self.placed[(x, y)] != ch:
            raise SystemExit(f"CELL COLLISION ({x},{y}): {self.placed[(x,y)]!r} vs {ch!r}")
        self.placed[(x, y)] = ch; self.p.put(x, y, ch)
        if bind is not None: self.intent[(x, y)] = bind
    def run(self, x, y, s):
        for i, ch in enumerate(s): self.C(x + i, y, ch)
    def pipeC(self, points, end_direction=None):
        cells = []
        for i in range(len(points) - 1):
            (x0, y0), (x1, y1) = points[i], points[i + 1]
            dx = (x1 > x0) - (x1 < x0); dy = (y1 > y0) - (y1 < y0)
            assert dx == 0 or dy == 0, f"diag {points[i]}->{points[i+1]}"
            for k in range(abs(x1 - x0) + abs(y1 - y0)):
                cells.append((x0 + dx * k, y0 + dy * k, dx, dy))
        lx, ly = points[-1]
        cells.append((lx, ly, cells[-1][2], cells[-1][3]))
        if end_direction:
            dx, dy = lm.DIRS[end_direction]; cells[-1] = (lx, ly, dx, dy)
        for idx, (x, y, dx, dy) in enumerate(cells):
            bend = idx > 0 and (cells[idx-1][2], cells[idx-1][3]) != (dx, dy)
            ch = (lm.VEC2ARROW[(dx, dy)] if (idx == 0 or idx == len(cells)-1 or bend)
                  else ("-" if dx != 0 else "|"))
            cur = self.p.get(x, y)
            if cur != " " and cur != ch:
                raise SystemExit(f"PIPE COLLISION ({x},{y}): existing {cur!r} vs pipe {ch!r}")
            self.C(x, y, ch)

def serp_pts(entry, x_lo, x_hi, y_from, y_to):
    pts = [entry]; at, y = entry[0], y_from
    step = 1 if y_to > y_from else -1
    while True:
        tgt = x_hi if abs(at - x_lo) < abs(at - x_hi) else x_lo
        pts.append((tgt, y)); at = tgt
        if y == y_to: break
        y += step; pts.append((at, y))
    return pts

AR, INA, BFS, MR, MF, KR, KF, AF = 2, 4, 6, 8, 10, 14, 15, 16
CIN, CRET, HA, OUTA = 3, 4, 5, 6
SOUTH = 19

def build():
    b = B(); C = b.C
    b.p.room(0, 0, 18, 19)          # CTRL interior x1..16, y1..17
    b.p.room(20, 0, 12, 8)          # W interior x21..30, y1..6
    b.p.room(33, 1, 9, 4)           # BRT interior x34..40, y2..3

    # ---------------- CTRL: S0 (rows 1-5) ----------------
    C(1,1,"@"); C(2,1,"."); C(3,1,".")
    C(4,1,"r",bind=(INA,-1)); C(5,1,"M"); C(6,1,"v")          # A=N, B=N
    C(6,2,"<"); C(5,2,"."); C(4,2,"r",bind=(INA,-1))          # A=M
    C(3,2,"."); C(2,2,"v")
    C(2,3,">")
    for x in range(3,10): C(x,3,".")
    C(10,3,"s",bind=(MF,-1))                                   # M-ring=[M]
    C(11,3,"v")
    C(11,4,"<")
    for x in range(5,11): C(x,4,".")
    C(4,4,"r",bind=(INA,-1))                                   # A=K
    C(3,4,"."); C(2,4,"v")
    C(2,5,">")
    for x in range(3,15): C(x,5,".")
    C(15,5,"s",bind=(KF,-1))                                   # K-ring=[K]
    C(16,5,"v")

    # ---------------- a-seed: outer xN with 150 markers ----------------
    # outer-head westbound row 6: reload BP=M from the M ring
    C(16,6,"<")
    for x in range(11,16): C(x,6,".")
    C(10,6,"s",bind=(MF,-1))          # recycle M   (s BEFORE r westbound: need r first!)
    C(9,6,".")
    C(8,6,"r",bind=(MR,-1))           # A=M  -- WRONG ORDER (fixed by loop shape):
    # NOTE: westbound hits s@10 before r@8; but on the FIRST pass A=K (from S0)
    # would be pushed to Mf. Instead route: row 6 only glides to (8,6); the
    # recycle s sits on row 7 eastbound.
    raise SystemExit("SEED-ORDER: see build_p2 notes")

if __name__ == "__main__":
    build()
