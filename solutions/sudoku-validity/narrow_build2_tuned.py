"""ringfree4: tick-optimized refold of the BOX compute man's hot loop.

Pure fold of ringfree3 (narrow_build.py): op multiset + order BYTE-IDENTICAL, only
the glide arrows / turn placement of the box-constraint compute man change.

The box man is the sole bottleneck (profiler: op46/turn22/glide28/stall4). Two path
cuts, both verified by tracing the man's cycle:
  (1) WEST-FIRST pre-op serpentine -> the loop re-enters at the top-RIGHT via a
      1-cell riser hop instead of gliding the whole top row back to the top-LEFT
      (kills ~10 glide + the y5 pre-op glide-back).
  (2) tighter 3-row pre-op pack (9-wide cols2-10) instead of 4 rows.
The champion's proven lane1/lane2 tail-fold (cL1=5, cL2=9) is kept verbatim so the
send routing / stacked checks in build_full are unchanged; only the box input tap
column moves (col3 -> col10) to match the West-first entry.

Box-man cycle: 90 cells -> 70 cells (43 op / 17 turn / 10 glide). Room 12->10 tall.
Row/col men + all cold structure identical to ringfree3.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
sys.path.insert(0, _REPO + '/solutions/sudoku-validity')
from littleman import Program
import narrow_build as NB

OPS_BOX = (list("rM3W/M9*Mr+M3W/M9*Mr+M1W-M")
           + list("1{ss")
           + ['W', 'M', '`', '6', '4', '`', 'W', '-', 'M', '1', '{', 's', 's'])
ARR = {'>': (1, 0), '<': (-1, 0), 'v': (0, 1), '^': (0, -1)}


def box_grid(W=14):
    """Hand-laid tight box compute man. Returns dict(cells,H,cL1,cL2,W,inx).
    Op ORDER verified by tracing the man cycle == OPS_BOX."""
    cells = {}
    pos = {}
    oi = [0]

    def put(x, y, g):
        if (x, y) in cells and cells[(x, y)] != g:
            raise SystemExit(f"box collide {(x,y)} {cells[(x,y)]} vs {g}")
        cells[(x, y)] = g

    def place(x, y):
        put(x, y, OPS_BOX[oi[0]]); pos[oi[0]] = (x, y); oi[0] += 1

    # pre-ops WEST-first serpentine, rows y1-3, cols 2-10
    for x in range(10, 1, -1):
        place(x, 1)                      # row1 W: op0-8
    put(1, 1, 'v'); put(1, 2, '>')
    for x in range(2, 11):
        place(x, 2)                      # row2 E: op9-17
    put(11, 2, 'v'); put(11, 3, '<')
    for x in range(10, 2, -1):
        place(x, 3)                      # row3 W: op18-25 (pre-ops done)
    put(2, 3, 'v'); put(2, 4, '>')
    # tail (champion structure): lane1, glide-back, lane2 `64`, fold, lane2 ss
    for x in range(3, 7):
        place(x, 4)                      # op26-29: 1 { s s  -> lane1 ss@5,6 (cL1=5)
    put(7, 4, 'v'); put(7, 5, '<')
    for x in (6, 5, 4):
        put(x, 5, ' ')                   # glide-back
    put(3, 5, 'v'); put(3, 6, '>')
    for x in range(4, 10):
        place(x, 6)                      # op30-35: W M ` 6 4 `  (literal@6-9)
    put(10, 6, 'v'); put(10, 7, '<')
    for x in (9, 8, 7):
        place(x, 7)                      # op36-38: W - M
    put(6, 7, 'v'); put(6, 8, '>')
    for x in range(7, 11):
        place(x, 8)                      # op39-42: 1 { s s -> lane2 ss@9,10 (cL2=9)
    # return: riser col12 up, re-enter top-right; spawn @ at (11,1)
    put(11, 8, '>'); put(12, 8, '^')
    for yy in range(7, 1, -1):
        put(12, yy, ' ')
    put(12, 1, '<'); put(11, 1, '@')
    assert oi[0] == len(OPS_BOX), oi[0]

    H = max(y for _, y in cells) + 2
    cL1 = pos[28][0]; cL2 = pos[41][0]; inx = pos[0][0]
    assert (cL1, cL2, inx) == (5, 9, 10), (cL1, cL2, inx)
    _verify_order(cells)
    return dict(cells=cells, H=H, cL1=cL1, cL2=cL2, W=W, inx=inx)


def _verify_order(cells):
    x, y = 11, 1; dx, dy = 1, 0
    hist = {}; ops = []; step = 0
    while step < 2000:
        st = (x, y, dx, dy)
        if st in hist:
            loop = hist[st]; break
        hist[st] = len(ops) if False else step
        ch = cells.get((x, y))
        if ch is None:
            raise SystemExit(f"box man ran off at {(x,y)}")
        if ch in ARR:
            dx, dy = ARR[ch]
        elif ch not in ' @':
            ops.append((step, ch))
        x, y = x + dx, y + dy; step += 1
    # take ops whose step >= loopstart
    loopops = ''.join(c for s, c in ops if s >= loop)
    if loopops != ''.join(OPS_BOX):
        raise SystemExit(f"BOX ORDER MISMATCH\n got {loopops}\nwant {''.join(OPS_BOX)}")


def build_full(path, P=14):
    prog = Program()
    lays = [NB.lay_narrow('row'), NB.lay_narrow('col'), box_grid()]
    Sx = [0 + i * P for i in range(3)]
    DY = 6
    DXO = 5
    Wtot = Sx[-1] + 14
    import importlib.util as ilu
    spec = ilu.spec_from_file_location('rf1', _REPO + '/solutions/sudoku-validity/ringfree_build.py')
    rf1 = ilu.module_from_spec(spec); spec.loader.exec_module(rf1)
    dist_south = rf1.distributor(prog, DXO, 0, Wtot - DXO)
    for i, lay in enumerate(lays):
        NB.place_room_cells(prog, Sx[i], DY, lay)
    Sc = [DY + lays[i]['H'] - 1 for i in range(3)]
    for i in range(3):
        inx = Sx[i] + lays[i].get('inx', 3)
        inx = max(inx, DXO + 1)
        prog.pipe([(inx, dist_south + 1), (inx, DY - 1)])
    dup_pipes = []
    band_low_south = []
    for i in range(3):
        sx = Sx[i]
        cL1 = sx + lays[i]['cL1']
        cL2 = sx + lays[i]['cL2']
        U = Sc[i] + 3
        L = U + 5
        NB.check_man(prog, sx, U)
        NB.check_man(prog, sx + 6, L)
        prog.pipe([(cL1, Sc[i] + 1), (cL1, U - 1)])
        prog.pipe([(cL2, Sc[i] + 1), (cL2, L - 1)])
        dup_pipes.append((sx + 2, U + 3))
        dup_pipes.append((sx + 11, L + 3))
        band_low_south.append(L + 3)
    import ringfree2_build as R
    MG = max(band_low_south) + 3
    mg_south, o_col = R.merger6(prog, 0, MG, Wtot)
    for (col, frow) in dup_pipes:
        prog.pipe([(col, frow + 1), (col, MG - 1)])
    prog.input_room(0, 0)
    prog.pipe([(3, 1), (DXO - 1, 1)])
    prog.output_room(o_col - 1, mg_south + 3)
    prog.pipe([(o_col, mg_south + 1), (o_col, mg_south + 2)])
    open(path, 'w').write(prog.render() + '\n')
    print('FOOT', prog.footprint())
    return prog


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else _REPO + '/solutions/sudoku-validity/ringfree4.man'
    build_full(out)
