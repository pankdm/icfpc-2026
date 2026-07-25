"""Build a NARROW-compute-man shift-OOB sudoku validator with STACKED checks.

Design = ringfree2's proven shift-OOB algorithm (3 dual-lane compute men), but folded:
  - Each compute man is hand-laid W=14 (lane1 pipe col cL1=Sx+5, lane2 col cL2=Sx+9),
    op-stream BYTE-IDENTICAL to ringfree2 (validated 729/729 + 3000 random).
  - Per man the two checks are STACKED (lane1-check above lane2-check) inside the
    14-wide band, so 3 bands pack tight horizontally (pitch 15) instead of W=20 x pitch23.
  - lane2 pipe + lane1 dup-flag route through the band (pass-through, mirrors ringfree PA/PB).
  - distributor (broadcast rSrSrS) top, sign-safe merger6 bottom (unchanged from ringfree2).

Op-sequence identical -> generalizes to private cases; box shrinks 70x34 -> ~46x41.
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
sys.path.insert(0, '/Users/visenbaev/icfpc26/solutions/sudoku-validity')
from littleman import Program
import ringfree2_build as R

# ---- narrow compute man (hand-laid, deterministic tail) ----
PRE = {
    'row': ['r','M','9','*','M','r','r','+','M','1','W','-','M'],
    'col': ['r','r','M','9','*','M','r','+','M','1','W','-','M'],
    'box': ['r'] + [g if not isinstance(g, tuple) else g for g in R.boxidx_ops()] + R.bit_ops(),
}
def _gl(t):
    if isinstance(t, tuple): return None
    return {'ri':'r','rv':'r','rc':'r','rr':'r'}.get(t, t)
PRE['box'] = ['r'] + [_gl(t) for t in R.boxidx_ops()] + [_gl(t) for t in R.bit_ops()]

def lay_narrow(kind, W=14):
    XL = 1; XR = W - 3; RISER = W - 2
    cells = {}
    def put(x, y, g):
        if g == ' ':
            cells.setdefault((x, y), ' '); return
        if (x, y) in cells and cells[(x, y)] not in (' ', g):
            raise SystemExit(f'{kind} collision {(x,y)} {cells[(x,y)]} vs {g}')
        cells[(x, y)] = g
    put(XL, 1, '@'); put(XL+1, 1, 'v'); put(XL+1, 2, '>')
    st = {'x': XL+2, 'y': 2, 'd': 'E'}
    def adv(): st['x'] += 1 if st['d']=='E' else -1
    def wrap():
        x, y, d = st['x'], st['y'], st['d']
        if d == 'E':
            while x < XR: put(x, y, ' '); x += 1
            put(XR, y, 'v'); y += 1; put(XR, y, '<'); x = XR-1; d = 'W'
        else:
            while x > XL+1: put(x, y, ' '); x -= 1
            put(XL+1, y, 'v'); y += 1; put(XL+1, y, '>'); x = XL+2; d = 'E'
        st['x'], st['y'], st['d'] = x, y, d
    def can(n=1):
        return (st['d']=='E' and st['x']+n-1 <= XR-1) or (st['d']=='W' and st['x']-(n-1) >= XL+2)
    def place(g):
        if not can(): wrap()
        put(st['x'], st['y'], g); adv()
    for g in PRE[kind]:
        place(g)
    while not (st['d']=='E' and st['x']==XL+2):
        wrap()
    c0 = st['x']; Ty = st['y']
    # lane1: 1 { s s  (cL1=c0+2)
    put(c0, Ty, '1'); put(c0+1, Ty, '{'); put(c0+2, Ty, 's'); put(c0+3, Ty, 's')
    cL1 = c0 + 2
    put(c0+4, Ty, 'v'); put(c0+4, Ty+1, '<')
    for x in range(c0+3, c0, -1): put(x, Ty+1, ' ')
    put(c0, Ty+1, 'v'); put(c0, Ty+2, '>')
    # lane2 block base=c0+1, 3-row fold, sends at cL2=c0+6
    # op-stream BYTE-IDENTICAL to validated ringfree2: W M `64` W - M 1 { s s
    x = c0+1
    for g in ['W','M','`','6','4','`']: put(x, Ty+2, g); x += 1
    put(c0+7, Ty+2, 'v'); put(c0+7, Ty+3, '<')
    put(c0+6, Ty+3, 'W'); put(c0+5, Ty+3, '-'); put(c0+4, Ty+3, 'M')
    put(c0+3, Ty+3, 'v'); put(c0+3, Ty+4, '>')
    put(c0+4, Ty+4, '1'); put(c0+5, Ty+4, '{')
    put(c0+6, Ty+4, 's'); put(c0+7, Ty+4, 's')
    cL2 = c0 + 6
    lane = Ty+4; ex = c0+7
    put(ex+1, lane, '>')
    for xx in range(ex+2, RISER): put(xx, lane, ' ')
    put(RISER, lane, '^')
    for yy in range(lane-1, 1, -1): put(RISER, yy, ' ')
    put(RISER, 1, '<')
    for xx in range(RISER-1, XL+1, -1): put(xx, 1, ' ')
    H = max(y for _, y in cells) + 2
    return dict(cells=cells, H=H, cL1=cL1, cL2=cL2, W=W)

def place_room_cells(prog, x0, y0, lay):
    prog.room(x0, y0, lay['W'], lay['H'])
    for (x, y), g in lay['cells'].items():
        if g == ' ': continue
        prog.put(x0+x, y0+y, g)

# ---- check man (8x4) with explicit dup-output column ----
def check_man(prog, sx, sy):
    """Room (sx,sy,8,4). r&s r|M. input attaches any wall near the r's; dup 's' -> nearest outgoing."""
    prog.room(sx, sy, 8, 4)
    a, b = sy+1, sy+2
    prog.put(sx+1,a,'@'); prog.put(sx+2,a,'>'); prog.put(sx+3,a,'r'); prog.put(sx+4,a,'&'); prog.put(sx+5,a,'s'); prog.put(sx+6,a,'v')
    prog.put(sx+2,b,'^'); prog.put(sx+3,b,'M'); prog.put(sx+4,b,'|'); prog.put(sx+5,b,'r'); prog.put(sx+6,b,'<')

def build_full(path, P=14):
    prog = Program()
    KINDS = ['row', 'col', 'box']
    lays = [lay_narrow(k) for k in KINDS]
    Sx = [1 + i*P for i in range(3)]        # bands hug the left (col1)
    DY = 6
    DXO = 5                                  # distributor west wall col (I room in cols0-2)
    Wtot = Sx[-1] + 14                       # merger/dist east wall == band2 east wall col
    import importlib.util as ilu
    spec = ilu.spec_from_file_location('rf1', '/Users/visenbaev/icfpc26/solutions/sudoku-validity/ringfree_build.py')
    rf1 = ilu.module_from_spec(spec); spec.loader.exec_module(rf1)
    dist_south = rf1.distributor(prog, DXO, 0, Wtot - DXO)   # top, cols DXO..Wtot-1
    # compute men
    for i, lay in enumerate(lays):
        place_room_cells(prog, Sx[i], DY, lay)
    Sc = [DY + lays[i]['H'] - 1 for i in range(3)]
    # dist -> compute (north wall). band0 input col must be >= DXO+1 (under distributor).
    for i in range(3):
        inx = max(Sx[i] + 3, DXO + 1)
        prog.pipe([(inx, dist_south+1), (inx, DY-1)])
    # per-band stacked checks + routing
    dup_pipes = []      # (col, from_row) for each dup -> merger
    band_low_south = []
    for i in range(3):
        sx = Sx[i]
        cL1 = sx + lays[i]['cL1']    # sx+5
        cL2 = sx + lays[i]['cL2']    # sx+9
        U = Sc[i] + 3                # upper check north wall
        L = U + 5                    # lower check north wall
        # upper check cols [sx .. sx+7], cL1 on north wall
        check_man(prog, sx, U)
        # lower check cols [sx+6 .. sx+13], cL2 on north wall
        check_man(prog, sx+6, L)
        # lane1 pipe -> upper check north (col cL1)
        prog.pipe([(cL1, Sc[i]+1), (cL1, U-1)])
        # lane2 pipe -> lower check north (col cL2), passing east of upper check (gap col sx+8)
        prog.pipe([(cL2, Sc[i]+1), (cL2, L-1)])
        # upper-check dup: south wall col sx+2 -> merger
        dup_pipes.append((sx+2, U+3))
        # lower-check dup: south wall col sx+11 -> merger
        dup_pipes.append((sx+11, L+3))
        band_low_south.append(L+3)
    MG = max(band_low_south) + 3
    mg_south, o_col = R.merger6(prog, 0, MG, Wtot)
    for (col, frow) in dup_pipes:
        prog.pipe([(col, frow+1), (col, MG-1)])
    # I room: top-left (cols0-2 rows0-2); 2-cell pipe east into distributor west wall
    prog.input_room(0, 0)
    prog.pipe([(3, 1), (DXO-1, 1)])
    # O room below merger
    prog.output_room(o_col-1, mg_south+3)
    prog.pipe([(o_col, mg_south+1), (o_col, mg_south+2)])
    open(path, 'w').write(prog.render()+'\n')
    print('FOOT', prog.footprint())
    return prog

if __name__ == '__main__':
    P = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    build_full('/private/tmp/claude-501/-Users-visenbaev-icfpc26/45d36e33-5a95-458c-9599-9b3faeeb9c09/scratchpad/narrow_full.man', P)
