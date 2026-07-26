"""Build solutions/sudoku-validity/ringfree2.man — SHIFT-OOB 3-compute-man validator.

Each compute man (ROW/COL/BOX): bit = 9*idx + (v-1); idx = r / c / box.
  lane1 = 1<<bit         (shl->0 if bit>63)   -> lane-1 check-man (low 64 bits)
  lane2 = 1<<(bit-64)    (shl->0 if bit<64)   -> lane-2 check-man (high 17 bits)
Register-clean: hold only `bit`, do two independent shifts from 1. No branch, no hold.
Math validated 729/729 + 3000 random boards (scratchpad/computeman3.py).

Targeted distributor: row-man<-r, col-man<-c, box-man<-r&c (computes box), v broadcast.
6 check men (r&s r|M) + merger unchanged.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from littleman import Program
from layout import Layout, place_pipe

# op tokens: single glyphs, or ('lit64',) macro (4 horizontal cells ` 6 4 `),
# 's1' = send to lane1 pipe, 's2' = send to lane2 pipe, 'ri'=read idx, 'rv'=read v.
def bit_ops():
    # A=idx -> B=bit .  (M 9 * M rv + M 1 W - M)
    return ['M', '9', '*', 'M', 'rv', '+', 'M', '1', 'W', '-', 'M']
def lane1_ops():   # B=bit -> A=1<<bit ; send x2
    return ['1', '{', 's1', 's1']
def lane2_ops():   # B=bit -> A=1<<(bit-64) ; send x2   (W M `64` W - M 1 {)
    return ['W', 'M', ('lit64',), 'W', '-', 'M', '1', '{', 's2', 's2']
def boxidx_ops():  # A=r ; reads c -> A=box=(c+9*(r//3))//3
    return ['M', '3', 'W', '/', 'M', '9', '*', 'M', 'rv', '+', 'M', '3', 'W', '/']
    # NOTE 'rv' here is actually 'read c'; box reads r(idx) then c then v.

def compute_stream(kind, broadcast=True):
    """broadcast=True: distributor sends r,c,v to ALL; each man reads 3 (discards unneeded).
    broadcast=False (targeted): man reads only [idx,v] (row/col) or [r,c,v] (box)."""
    if broadcast:
        if kind == 'row':   # read r(idx); 9*r; read c(discard); read v; +
            pre = ['ri', 'M', '9', '*', 'M', 'rc', 'rv', '+', 'M', '1', 'W', '-', 'M']
        elif kind == 'col': # read r(discard); read c(idx); 9*c; read v; +
            pre = ['rr', 'ri', 'M', '9', '*', 'M', 'rv', '+', 'M', '1', 'W', '-', 'M']
        else:               # box: read r; boxidx(reads c); bit(reads v)
            pre = ['ri'] + boxidx_ops() + bit_ops()
        return pre + lane1_ops() + lane2_ops()
    if kind in ('row', 'col'):
        return ['ri'] + bit_ops() + lane1_ops() + lane2_ops()
    return ['ri'] + boxidx_ops() + bit_ops() + lane1_ops() + lane2_ops()

def tok_len(t):
    return 4 if (isinstance(t, tuple) and t[0] == 'lit64') else 1

def glyph(t):
    if isinstance(t, tuple): return None
    return {'ri': 'r', 'rv': 'r', 'rc': 'r', 'rr': 'r', 's1': 's', 's2': 's', '{': '{'}.get(t, t)

# ---------------------------------------------------------------------------
def lay_compute3(kind, W, cL1=None, cL2=None):
    """Compact hand-laid compute man. lane1-pipe SOUTH col cL1, lane2-pipe SOUTH col cL2
    (far apart -> unambiguous send discipline). Bit+lane1 shift as a boustrophedon; then
    s1 s1 down cL1; lane2 shift ops (serpentined, `64` kept horizontal); s2 s2 down cL2.
    Returns dict(cells,H,cL1,cL2,W)."""
    XL = 1; XR = W - 3; RISER = W - 2
    if cL1 is None: cL1 = XL + 1        # far west
    if cL2 is None: cL2 = RISER - 1     # far east
    cells = {}
    def put(x, y, g):
        if g == ' ':
            cells.setdefault((x, y), ' '); return
        if (x, y) in cells and cells[(x, y)] not in (' ', g):
            raise SystemExit(f'{kind} collision {(x,y)} {cells[(x,y)]} vs {g}')
        cells[(x, y)] = g
    put(XL, 1, '@'); put(XL + 1, 1, 'v'); put(XL + 1, 2, '>')
    st = {'x': XL + 2, 'y': 2, 'd': 'E'}
    def adv(): st['x'] += 1 if st['d'] == 'E' else -1
    def wrap():
        x, y, d = st['x'], st['y'], st['d']
        if d == 'E':
            while x < XR: put(x, y, ' '); x += 1
            put(XR, y, 'v'); y += 1; put(XR, y, '<'); x = XR - 1; d = 'W'
        else:
            while x > XL + 1: put(x, y, ' '); x -= 1
            put(XL + 1, y, 'v'); y += 1; put(XL + 1, y, '>'); x = XL + 2; d = 'E'
        st['x'], st['y'], st['d'] = x, y, d
    def can_place(n=1):
        if st['d'] == 'E': return st['x'] + n - 1 <= XR - 1
        else: return st['x'] - (n - 1) >= XL + 2
    def place(g):
        if not can_place(): wrap()
        put(st['x'], st['y'], g); adv()
    def place_lit64():
        if not can_place(4): wrap()
        for g in ['`', '6', '4', '`']:
            put(st['x'], st['y'], g); adv()
    # tokens; render s1/s2 as plain 's' but record where they land
    toks = compute_stream(kind)
    s1cells = []; s2cells = []
    for t in toks:
        if isinstance(t, tuple):
            place_lit64(); continue
        if t == 's1':
            place('s'); s1cells.append((st['x'] - (1 if st['d']=='E' else -1), st['y'])); continue
        if t == 's2':
            place('s'); s2cells.append((st['x'] - (1 if st['d']=='E' else -1), st['y'])); continue
        place(glyph(t))
    # loop-back
    x, y = st['x'], st['y']
    put(x, y, 'v'); Yb = y + 1
    put(x, Yb, '>')
    for xx in range(x + 1, RISER): put(xx, Yb, ' ')
    put(RISER, Yb, '^')
    for yy in range(Yb - 1, 1, -1): put(RISER, yy, ' ')
    put(RISER, 1, '<')
    for xx in range(RISER - 1, XL + 1, -1): put(xx, 1, ' ')
    H = max(yy for (_, yy) in cells) + 2
    # pipe cols = actual send-cell columns (they define nearest-discipline midpoint)
    cL1 = min(c for c, _ in s1cells); cL2 = max(c for c, _ in s2cells)
    return dict(cells=cells, H=H, cL1=cL1, cL2=cL2, W=W)

def place_room_cells(prog, x0, y0, lay):
    W, H = lay['W'], lay['H']
    prog.room(x0, y0, W, H)
    for (x, y), g in lay['cells'].items():
        if g == ' ': continue
        prog.put(x0 + x, y0 + y, g)
    return H

if __name__ == '__main__' and len(sys.argv) == 1:
    for kind in ('row', 'col', 'box'):
        try:
            lay = lay_compute3(kind, 20)
            p = Program(); place_room_cells(p, 0, 0, lay)
            print(f'=== {kind} W20 H={lay["H"]} cL1={lay["cL1"]} cL2={lay["cL2"]} ===')
            print(p.render())
        except SystemExit as e:
            print(kind, 'ERR', e)

# ---------------------------------------------------------------------------
def check_man(prog, sx, sy):
    """Compact 4-tall check man (r & s r | M). Room (sx,sy,8,4). 1 in, 1 out (any wall)."""
    prog.room(sx, sy, 8, 4)
    a, b = sy + 1, sy + 2
    prog.put(sx+1,a,'@'); prog.put(sx+2,a,'>'); prog.put(sx+3,a,'r'); prog.put(sx+4,a,'&'); prog.put(sx+5,a,'s'); prog.put(sx+6,a,'v')
    prog.put(sx+2,b,'^'); prog.put(sx+3,b,'M'); prog.put(sx+4,b,'|'); prog.put(sx+5,b,'r'); prog.put(sx+6,b,'<')

def merger2(prog, x0, y0, W=12):
    """2-input merger for isolation test: R M R | X ; ok->1 s loop ; dup->0 s H."""
    prog.room(x0, y0, W, 7)
    tr, st = y0+1, y0+2
    prog.put(x0+1,tr,'@'); prog.put(x0+2,tr,'v'); prog.put(x0+2,st,'>')
    for i,ch in enumerate(['R','M','R','|']): prog.put(x0+3+i,st,ch)  # cols 3-6
    xc=x0+7; prog.put(xc,st,'X')                                      # col7
    prog.put(xc+1,st,'1'); prog.put(xc+2,st,'s'); ocol=xc+2           # ok: cols 8,9
    prog.put(x0+10,st,'^'); prog.put(x0+10,tr,'<')                    # loop riser col10
    prog.put(xc,st+1,'0'); prog.put(xc,st+2,'s'); prog.put(xc,st+3,'H')  # dup down col7
    return y0+6, ocol

def build_test(kind, path):
    prog = Program()
    W = 20
    lay = lay_compute3(kind, W)
    cx, cy = 6, 0
    place_room_cells(prog, cx, cy, lay)
    csouth = cy + lay['H'] - 1
    cL1 = cx + lay['cL1']; cL2 = cx + lay['cL2']
    # input to compute (west wall)
    prog.input_room(0, cy+2)
    prog.pipe([(3, cy+3), (cx-1, cy+3)])
    # two checks below, fed by lane pipes
    chy = csouth + 3
    check_man(prog, cL1-3, chy)      # lane1 check (bit-in north at cL1)
    check_man(prog, cL2-3, chy)      # lane2 check
    prog.pipe([(cL1, csouth+1),(cL1, chy-1)])
    prog.pipe([(cL2, csouth+1),(cL2, chy-1)])
    # dup pipes down to merger (check south wall at chy+3; pipe starts chy+4)
    my = chy + 4 + 3
    msouth, ocol = merger2(prog, 0, my, W=max(cL1, cL2) + 3)
    prog.pipe([(cL1, chy+4),(cL1, my-1)])
    prog.pipe([(cL2, chy+4),(cL2, my-1)])
    prog.output_room(ocol-1, msouth+3)
    prog.pipe([(ocol, msouth+1),(ocol, msouth+2)])
    open(path,'w').write(prog.render()+'\n')
    return prog

if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'test':
    import subprocess
    kind = sys.argv[2] if len(sys.argv) > 2 else 'row'
    path = f'{_REPO}/scratchpad/cm3_{kind}.man'
    build_test(kind, path)
    # craft input for the kind: two cells that duplicate in THIS kind
    if kind == 'row':   cells = [(0,0,5),(3,1,4),(0,7,5)]   # row0 v5 twice -> dup at cell2
    elif kind == 'col': cells = [(0,0,5),(1,3,4),(7,0,5)]   # col0 v5 twice
    else:               cells = [(0,0,5),(1,4,4),(1,1,5)]   # box0 v5 twice (r,c in 0-2)
    exp = ['1','1','0']
    # broadcast: every man reads r,c,v
    inp = ' / '.join(f'{r} {c} {v}' for r,c,v in cells)
    ex = ' / '.join(exp)
    out = subprocess.run(['interp/target/release/lm','--grade',path,f'--input={inp}',f'--expected={ex}','--cap=100000'],
                         cwd=_REPO, capture_output=True, text=True)
    print(kind, out.stdout.strip()[:200])

# ===========================================================================
# FULL BUILD: distributor(broadcast) -> 3 compute -> 6 check -> merger
# ===========================================================================
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location('rf1', _REPO + '/solutions/sudoku-validity/ringfree_build.py')
rf1 = _ilu.module_from_spec(_spec); _spec.loader.exec_module(rf1)

def build_full(path, CW=20):
    L = Layout()
    KINDS = ['row', 'col', 'box']
    lays = [lay_compute3(k, CW) for k in KINDS]
    Hc = max(l['H'] for l in lays)
    P = CW + 3
    Cx = [3 + i * P for i in range(3)]           # compute-man room origins
    DY = 6                                        # compute north wall
    for i, lay in enumerate(lays):
        place_room_cells(L, Cx[i], DY, lay)
    comp_south = [DY + lays[i]['H'] - 1 for i in range(3)]
    # lane pipe columns (absolute)
    lane_cols = []
    for i, lay in enumerate(lays):
        lane_cols.append((Cx[i] + lay['cL1'], Cx[i] + lay['cL2']))
    # ---- distributor (broadcast, full width) above ----
    Wtot = Cx[-1] + CW + 1
    dist_south = rf1.distributor(L, 0, 0, Wtot)   # H=4, south wall row3
    for i in range(3):
        # dist -> compute: pick the compute man's IN col = its feeder read col (3) on north wall
        inx = Cx[i] + 3
        L.pipe([(inx, dist_south + 1), (inx, DY - 1)])
    # ---- 6 check men below (2 per compute at its lane cols) ----
    CHY = max(comp_south) + 3
    for i in range(3):
        c1, c2 = lane_cols[i]
        check_man(L, c1 - 3, CHY)                # lane1 check
        check_man(L, c2 - 3, CHY)                # lane2 check
        L.pipe([(c1, comp_south[i] + 1), (c1, CHY - 1)])
        L.pipe([(c2, comp_south[i] + 1), (c2, CHY - 1)])
    check_south = CHY + 3
    # ---- merger (full width) ----
    MY = check_south + 3
    mg_south, o_col = merger6(L, 0, MY, Wtot)
    for i in range(3):
        for c in lane_cols[i]:
            L.pipe([(c, check_south + 1), (c, MY - 1)])
    # ---- I room: tuck in left margin below distributor ----
    L.input_room(0, DY)
    place_pipe(L, [(1, DY - 1), (1, dist_south + 1)], (0, -1))
    # ---- O room below merger ----
    L.output_room(o_col - 1, mg_south + 3)
    L.pipe([(o_col, mg_south + 1), (o_col, mg_south + 2)])
    L.save(path)
    print('FOOT', L.footprint())
    return L

if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'full':
    build_full(_REPO + '/scratchpad/ringfree2_full.man')

def merger6(prog, x0, y0, W):
    """6-input merger with SIGN-SAFE nonzero detection (handles 1<<63 dup flags).
    OR 6 dups -> A ; nz = ((A|(-A))>>63) negated -> 1 iff A!=0, 0 iff A==0 ; X: >0 dup, 0 ok.
    ops: R M (R|M)x4 R|  M N |  M `63` W } N  X  ...  Returns (south_row, o_col)."""
    H = 7
    prog.room(x0, y0, W, H)
    tr, st = y0 + 1, y0 + 2
    prog.put(x0+1, tr, '@'); prog.put(x0+2, tr, 'v'); prog.put(x0+2, st, '>')
    ops = ['R','M'] + ['R','|','M']*4 + ['R','|']          # OR of 6 (16)
    ops += ['M','N','|']                                   # A|(-A)  (<=0, <0 iff A!=0)
    ops += ['M','`','6','3','`','W','}','N']               # ((A|(-A))>>63) then negate -> 1/0
    x = x0 + 3
    for ch in ops:
        prog.put(x, st, ch); x += 1
    prog.put(x, st, 'X'); xc = x
    prog.put(xc+1, st, '1'); prog.put(xc+2, st, 's'); ocol = xc+2      # ok: 1 s
    prog.put(xc+3, st, '^'); prog.put(xc+3, tr, '<')                   # loop riser
    prog.put(xc, st+1, '0'); prog.put(xc, st+2, 's'); prog.put(xc, st+3, 'H')  # dup: 0 s H
    return y0 + H - 1, ocol
