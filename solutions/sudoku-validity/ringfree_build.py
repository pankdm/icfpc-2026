"""Build solutions/sudoku-validity/ringfree.man — RING-FREE distributed sudoku validator.

Design (eliminate the central scratch ring):
  I -> DISTRIBUTOR (read r,c,v; broadcast each via S to all 6 compute men)
     -> 6 COMPUTE men (each derives ONE bit locally in A/B, NO ring; rk parked in BP;
        sends the bit TWICE to its store man)
        -> 6 STORE men (mask in B; proven  r & s r | M  dup-check; dup-flag -> merger)
           -> MERGER (R-reads 6 dup flags, ORs; dup>0 -> out 0 + H; else out 1) -> O

Each compute man computes its bit with only A,B,BP:
  idx = r (row) / c (col) / box=(c+9*(r//3))//3 (box)
  core: field=idx%5, rk=idx//5 (rk->BP), 9*field kept in B; read v; shift=v+9field-1;
        base=1<<shift; branch on BP: Hi outputs base iff rk==1 else 0, Lo iff rk==0.
Per-man math validated 729/729 in scratchpad/computeman.py.
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from littleman import Program

# ---- op glyph streams (linear part, before the branch) ----
CORE = "M5W/bWM9*M"          # A=idx -> BP=rk, B=9*field  (10)
BOXIDX = "M3W/M9*Mr+M3W/"    # A=r, reads c -> A=box       (14, incl read c)
SHIFT = "M1W-M1{"            # A=v+9field -> A=base         (7)

def linear_glyphs(kind):
    if kind == 'row':   # read r; core; read c(discard); read v; +
        return "r" + CORE + "r" + "r" + "+" + SHIFT
    if kind == 'col':   # read r(discard); read c; core; read v; +
        return "r" + "r" + CORE + "r" + "+" + SHIFT
    if kind == 'box':   # read r; boxidx(reads c); core; read v; +
        return "r" + BOXIDX + CORE + "r" + "+" + SHIFT
    raise ValueError(kind)

# ---------------------------------------------------------------------------
def lay_compute(kind, hilo, W):
    """Lay a compute man as a boustrophedon serpentine + BP branch + loopback.
    Room is W wide. Incoming pipe attaches WEST wall; outgoing EAST wall.
    Returns dict(cells, H, in_row, out_row)."""
    glyphs = linear_glyphs(kind)
    XL = 1
    XR = W - 3          # east turn column (reserve W-2 riser, W-1 wall)
    RISER = W - 2
    cells = {}
    def put(x, y, g):
        if g == ' ':
            cells.setdefault((x, y), ' '); return
        if (x, y) in cells and cells[(x, y)] not in (' ', g):
            raise SystemExit(f'{kind}{hilo} collision {(x,y)} {cells[(x,y)]} vs {g}')
        cells[(x, y)] = g
    # feeder
    put(XL, 1, '@'); put(XL + 1, 1, 'v'); put(XL + 1, 2, '>')
    st = {'x': XL + 2, 'y': 2, 'd': 'E'}
    def adv():
        st['x'] += 1 if st['d'] == 'E' else -1
    def wrap():
        x, y, d = st['x'], st['y'], st['d']
        if d == 'E':
            while x < XR: put(x, y, ' '); x += 1
            put(XR, y, 'v'); y += 1; put(XR, y, '<'); x = XR - 1; d = 'W'
        else:
            while x > XL + 1: put(x, y, ' '); x -= 1
            put(XL + 1, y, 'v'); y += 1; put(XL + 1, y, '>'); x = XL + 2; d = 'E'
        st['x'], st['y'], st['d'] = x, y, d
    def can_place():
        return (st['d'] == 'E' and st['x'] <= XR - 1) or (st['d'] == 'W' and st['x'] >= XL + 2)
    for g in glyphs:
        if not can_place(): wrap()
        put(st['x'], st['y'], g); adv()
    # wrap to a FRESH East-heading row at col XL+2 for the branch (guarantees clean geometry)
    while not (st['d'] == 'E' and st['x'] == XL + 2):
        wrap()
    xc = st['x']                         # == XL+2
    Yb = st['y']                         # branch top row (fresh, empty below)
    # ---- BP branch gadget ----
    # (xc,Yb)=d heading E. rk==1 (BP>0) -> CW=South ; rk==0 -> straight East.
    put(xc, Yb, 'd')
    g0a = '0' if hilo == 'hi' else ' '   # straight arm (rk==0): Hi sends 0, Lo sends base
    g1a = ' ' if hilo == 'hi' else '0'   # CW arm (rk==1): Hi sends base, Lo sends 0
    put(xc + 1, Yb, g0a); put(xc + 2, Yb, 'v')          # straight arm -> south to rejoin row
    put(xc, Yb + 1, '>'); put(xc + 1, Yb + 1, g1a)      # CW arm heads E
    put(xc + 2, Yb + 1, '>')                            # rejoin: both head E
    put(xc + 3, Yb + 1, 's'); put(xc + 4, Yb + 1, 's')  # send bit twice
    # loopback: from (xc+4,Yb+1) heading E -> east to riser -> up to row1 -> west to entry 'v'
    lane = Yb + 1
    ex = xc + 4
    put(ex + 1, lane, '>')
    for xx in range(ex + 2, RISER): put(xx, lane, ' ')
    put(RISER, lane, '^')
    for yy in range(lane - 1, 1, -1): put(RISER, yy, ' ')
    put(RISER, 1, '<')
    for xx in range(RISER - 1, XL + 1, -1): put(xx, 1, ' ')
    H = max(y for (_, y) in cells) + 2
    # incoming pipe west wall: attach at an interior row (row 2 is fine — r's read nearest=only)
    in_row = 2
    out_row = lane
    return dict(cells=cells, H=H, in_row=in_row, out_row=out_row, W=W)

def place_room_cells(prog, x0, y0, lay):
    W, H = lay['W'], lay['H']
    prog.room(x0, y0, W, H)
    for (x, y), g in lay['cells'].items():
        if g == ' ': continue
        prog.put(x0 + x, y0 + y, g)
    return H

# ---------------------------------------------------------------------------
def distributor(prog, x0, y0, W):
    """Read r,c,v from the single incoming pipe (I); broadcast each via S to ALL
    outgoing pipes (the 6 compute-men pipes on the south wall). Loop: r S r S r S.
    Room spans full width W so its south wall reaches every compute man's column.
    Returns south-wall row."""
    prog.room(x0, y0, W, 5)
    a, b, c = y0 + 1, y0 + 2, y0 + 3
    prog.put(x0 + 1, a, '@'); prog.put(x0 + 2, a, 'v')
    ops = '>rSrSrS'
    for i, g in enumerate(ops):
        prog.put(x0 + 2 + i, b, g)
    endx = x0 + 2 + len(ops)             # cell after last op (S)
    prog.put(endx, b, 'v')               # drop south
    prog.put(endx, c, '<')               # loopback west
    prog.put(x0 + 2, c, '^')             # up into '>' at (x0+2,b)
    return y0 + 4                        # south wall row

def store_man(prog, f, y0):
    """Vertical storage man (proven r & s r | M). Room (f-2,y0,5,10).
    Bit pipe enters north (f,y0); dup exits south (f,y0+9)."""
    prog.room(f - 2, y0, 5, 10)
    prog.put(f - 1, y0 + 1, '@'); prog.put(f, y0 + 1, 'v'); prog.put(f + 1, y0 + 1, '<')
    for dy, ch in [(2, 'r'), (3, '&'), (4, 's'), (5, 'r'), (6, '|'), (7, 'M')]:
        prog.put(f, y0 + dy, ch)
    prog.put(f, y0 + 8, '>'); prog.put(f + 1, y0 + 8, '^')

def merger(prog, x0, y0, W):
    """Flat merger: OR of 6 dup flags (R=recv_any, position-free), then X:
      A==0 (ok, straight E)  -> 1 ; s->O ; loop back
      A>0  (dup, CW South)   -> 0 ; s->O ; H
    6 dup pipes attach the NORTH wall. Returns (south_row, o_col)."""
    H = 7
    prog.room(x0, y0, W, H)
    tr, st = y0 + 1, y0 + 2
    prog.put(x0 + 1, tr, '@'); prog.put(x0 + 2, tr, 'v'); prog.put(x0 + 2, st, '>')
    ops = ['R', 'M'] + ['R', '|', 'M'] * 4 + ['R', '|']
    x = x0 + 3
    for ch in ops:
        prog.put(x, st, ch); x += 1
    prog.put(x, st, 'X'); xc = x
    prog.put(xc + 1, st, '1'); prog.put(xc + 2, st, 's'); ocol = xc + 2
    riser = xc + 4
    prog.put(riser, st, '^'); prog.put(riser, tr, '<')
    prog.put(xc, st + 1, '0'); prog.put(xc, st + 2, 's'); prog.put(xc, st + 3, 'H')
    return y0 + H - 1, ocol

# ---------------------------------------------------------------------------
KINDS = [('row', 'lo'), ('row', 'hi'), ('col', 'lo'), ('col', 'hi'), ('box', 'lo'), ('box', 'hi')]

def build_full(path):
    prog = Program()
    Wm = 16                              # uniform man width (box needs 16)
    IN_COL = 3                           # north-wall input attach (interior col)
    OUT_COL = 6                          # south-wall output attach (interior col)
    PITCH = Wm + 3                       # per-man horizontal slot
    DY = 8                               # compute-men north wall row
    # ---- compute men row ----
    lays = []
    xslots = []
    maxH = 0
    for i, (kind, hilo) in enumerate(KINDS):
        lay = lay_compute(kind, hilo, Wm)
        x0 = 4 + i * PITCH
        place_room_cells(prog, x0, DY, lay)
        lays.append(lay); xslots.append(x0)
        maxH = max(maxH, lay['H'])
    comp_south = {i: DY + lays[i]['H'] - 1 for i in range(6)}   # each man's south wall
    # ---- distributor above (spans full width); 6 pipes down to each compute north wall ----
    dist_x = 0
    dist_W = xslots[-1] + Wm + 1 - dist_x
    dist_south = distributor(prog, dist_x, 0, dist_W)
    for i in range(6):
        inx = xslots[i] + IN_COL
        # pipe: distributor south wall -> down -> compute north wall (inx, DY)
        prog.pipe([(inx, dist_south + 1), (inx, DY - 1)])
    # ---- store men below each compute man ----
    STORE_GAP = 2
    store_y = DY + maxH + STORE_GAP
    for i in range(6):
        f = xslots[i] + OUT_COL
        store_man(prog, f, store_y)
        # pipe: compute south wall (f, comp_south[i]) -> store north (f, store_y)
        prog.pipe([(f, comp_south[i] + 1), (f, store_y - 1)])
    store_south = store_y + 9
    # ---- merger below, spanning full width; 6 dup pipes down ----
    merge_y = store_south + 3
    MW = xslots[-1] + Wm + 4
    mg_south, o_col = merger(prog, 0, merge_y, MW)
    for i in range(6):
        f = xslots[i] + OUT_COL
        prog.pipe([(f, store_south + 1), (f, merge_y - 1)])
    # ---- I room (left of distributor) -> distributor west wall ----
    inr = 2                              # distributor interior row for input (row y0+2=2)
    prog.input_room(dist_x - 5, inr - 1)
    prog.pipe([(dist_x - 2, inr), (dist_x - 1, inr)])
    # ---- O room below merger ----
    prog.output_room(o_col - 1, mg_south + 3)
    prog.pipe([(o_col, mg_south + 1), (o_col, mg_south + 2)])
    with open(path, 'w') as f:
        f.write(prog.render() + '\n')
    print('FOOT', prog.footprint())
    return prog

# ---------------------------------------------------------------------------
def build_single(kind, hilo, path):
    """Isolated test harness: I -> compute man -> O. Man sends bit twice; we expect
    the bit value repeated (out per round = the two sends). Actually round output must
    equal expected; we set expected to the two-send bit. Used to validate compute op-stream."""
    prog = Program()
    W = 16 if kind == 'box' else 14
    lay = lay_compute(kind, hilo, W)
    x0, y0 = 6, 3
    place_room_cells(prog, x0, y0, lay)
    # input room to the left, pipe into WEST wall interior row
    inr = y0 + lay['in_row']
    prog.input_room(0, inr - 1)                   # I room cols 0..2
    prog.pipe([(3, inr), (x0 - 1, inr)])          # I east wall -> compute west wall
    # output room to the right of east wall out_row
    outr = y0 + lay['out_row']
    ox = x0 + W
    prog.output_room(ox + 2, outr - 1)
    prog.pipe([(ox, outr), (ox + 1, outr)])
    with open(path, 'w') as f:
        f.write(prog.render() + '\n')
    return prog

if __name__ == '__main__':
    import subprocess
    # validate each kind/hilo in isolation on the Rust lm (few pipes -> lm is fine here)
    def ref_bit(kind, hilo, r, c, v):
        box = 3 * (r // 3) + (c // 3)
        idx = {'row': r, 'col': c, 'box': box}[kind]
        field = idx % 5; rk = idx // 5
        base = 1 << (9 * field + (v - 1))
        return base * (rk if hilo == 'hi' else (1 - rk))
    kinds = [('row', 'lo'), ('row', 'hi'), ('col', 'lo'), ('col', 'hi'), ('box', 'lo'), ('box', 'hi')]
    testpts = [(0, 0, 1), (4, 5, 4), (8, 8, 9), (5, 3, 7), (2, 6, 4), (7, 1, 9), (3, 3, 3)]
    allok = True
    for kind, hilo in kinds:
        path = f'/private/tmp/claude-501/-Users-visenbaev-icfpc26/45d36e33-5a95-458c-9599-9b3faeeb9c09/scratchpad/cm_{kind}_{hilo}.man'
        build_single(kind, hilo, path)
        # one round per test point; expected = bit repeated twice (two sends)
        inp = ' / '.join(f'{r} {c} {v}' for (r, c, v) in testpts)
        exp = ' / '.join(f'{ref_bit(kind,hilo,r,c,v)} {ref_bit(kind,hilo,r,c,v)}' for (r, c, v) in testpts)
        out = subprocess.run(['interp/target/release/lm', '--grade', path, f'--input={inp}', f'--expected={exp}', '--cap=200000'],
                             cwd='/Users/visenbaev/icfpc26', capture_output=True, text=True)
        status = out.stdout.strip()
        ok = '"status":"pass"' in status
        allok = allok and ok
        print(f'{kind}{hilo}: {"PASS" if ok else "FAIL"}  {status[:160]}')
    print('ALL OK' if allok else 'SOME FAILED')

# ===========================================================================
# FOLDED 2-band layout (3 cols x 2 rows) for a compact box.
# ===========================================================================
from layout import Layout, place_pipe

def _expand(waypoints):
    """Expand orthogonal waypoints to the full ordered cell list (for place_pipe)."""
    cells = [tuple(waypoints[0])]
    for i in range(len(waypoints) - 1):
        (x0, y0), (x1, y1) = waypoints[i], waypoints[i + 1]
        dx = (x1 > x0) - (x1 < x0); dy = (y1 > y0) - (y1 < y0)
        for k in range(1, abs(x1 - x0) + abs(y1 - y0) + 1):
            cells.append((x0 + dx * k, y0 + dy * k))
    return cells

def jog_pipe(L, waypoints, exit_dir):
    """L-bend pipe through waypoints, entering the dest room wall via exit_dir."""
    place_pipe(L, _expand(waypoints), exit_dir)

def store_compact(L, sx, sy):
    """Compact 4-tall store man (proven r & s r | M). Room (sx,sy,8,4).
    bit-in and dup-out attach any wall (1 incoming, 1 outgoing; r/s use nearest=only).
    Returns the room rect (sx,sy,8,4)."""
    L.room(sx, sy, 8, 4)
    a, b = sy + 1, sy + 2
    L.put(sx + 1, a, '@'); L.put(sx + 2, a, '>'); L.put(sx + 3, a, 'r'); L.put(sx + 4, a, '&'); L.put(sx + 5, a, 's'); L.put(sx + 6, a, 'v')
    L.put(sx + 2, b, '^'); L.put(sx + 3, b, 'M'); L.put(sx + 4, b, '|'); L.put(sx + 5, b, 'r'); L.put(sx + 6, b, '<')
    return (sx, sy, 8, 4)

def merger_flat(L, x0, y0, W):
    """Flat full-width merger; 6 dup pipes on NORTH wall (recv_any). Returns (south_row, o_col)."""
    H = 7
    L.room(x0, y0, W, H)
    tr, st = y0 + 1, y0 + 2
    L.put(x0 + 1, tr, '@'); L.put(x0 + 2, tr, 'v'); L.put(x0 + 2, st, '>')
    ops = ['R', 'M'] + ['R', '|', 'M'] * 4 + ['R', '|']
    x = x0 + 3
    for ch in ops:
        L.put(x, st, ch); x += 1
    L.put(x, st, 'X'); xc = x
    L.put(xc + 1, st, '1'); L.put(xc + 2, st, 's'); ocol = xc + 2
    riser = xc + 4
    L.put(riser, st, '^'); L.put(riser, tr, '<')
    L.put(xc, st + 1, '0'); L.put(xc, st + 2, 's'); L.put(xc, st + 3, 'H')
    return y0 + H - 1, ocol

def build_folded(path):
    L = Layout()
    Wm = 12
    P = 17
    Sx = [6, 6 + P, 6 + 2 * P]                 # man room origins: 6,23,40
    E = [s + Wm - 1 for s in Sx]               # east walls: 17,34,51
    # PA (dist->bot, enters man WEST wall) on the LEFT of each man;
    # PB (topstore->merger, exits store EAST) on the RIGHT — opposite sides so jogs never cross.
    PA = [4, Sx[0] + 15, Sx[1] + 15]           # 4,21,38  (left gap of each slot)
    PB = [Sx[0] + 13, Sx[1] + 13, Sx[2] + 13]  # 19,36,53 (right gap of each slot)
    TOP = KINDS[:3]                            # rowLo,rowHi,colLo
    BOT = KINDS[3:]                            # colHi,boxLo,boxHi
    # bands
    DIST_Y = 0; dist_south = DIST_Y + 4
    DY_t = 7                                   # top compute north
    # place top compute men
    top_lays = []
    for c, (kind, hilo) in enumerate(TOP):
        lay = lay_compute(kind, hilo, Wm)
        place_room_cells(L, Sx[c], DY_t, lay)
        top_lays.append(lay)
    top_c_south = [DY_t + top_lays[c]['H'] - 1 for c in range(3)]
    maxtop_south = max(top_c_south)
    TS_t = maxtop_south + 3                     # top store north (gap>=3)
    for c in range(3):
        store_compact(L, Sx[c] + 2, TS_t)      # store body Sx+2..Sx+9
    tstore_south = TS_t + 3
    DY_b = tstore_south + 3                     # bot compute north
    bot_lays = []
    for c, (kind, hilo) in enumerate(BOT):
        lay = lay_compute(kind, hilo, Wm)
        place_room_cells(L, Sx[c], DY_b, lay)
        bot_lays.append(lay)
    bot_c_south = [DY_b + bot_lays[c]['H'] - 1 for c in range(3)]
    maxbot_south = max(bot_c_south)
    TS_b = maxbot_south + 3                     # bot store north
    for c in range(3):
        store_compact(L, Sx[c] + 2, TS_b)
    bstore_south = TS_b + 3
    MG = bstore_south + 3                       # merger north
    Wtot = max(E[2], PB[2]) + 2                 # full width (include rightmost pass-through)
    mg_south, o_col = merger_flat(L, 0, MG, Wtot)
    # ---- distributor (full width, top) ----
    distributor(L, 0, DIST_Y, Wtot)
    # ---- I room -> distributor west wall ----
    inr = DIST_Y + 2
    L.input_room(-5, inr - 1)
    L.pipe([(-2, inr), (-1, inr)])
    # ============ PIPES ============
    for c in range(3):
        icol = Sx[c] + 3                        # compute local IN col (north)
        ocol = Sx[c] + 6                        # compute local OUT col (south)
        # dist -> TOP compute (straight down)
        L.pipe([(icol, dist_south + 1), (icol, DY_t - 1)])
        # TOP compute -> TOP store (straight down)
        L.pipe([(ocol, top_c_south[c] + 1), (ocol, TS_t - 1)])
        # TOP store -> merger via PB (EAST out of store, down PB to merger north)
        jog_pipe(L, [(Sx[c] + 10, TS_t + 1), (PB[c], TS_t + 1), (PB[c], MG - 1)], (0, 1))
        # dist -> BOT compute via PA (down PA, east into west wall)
        Wrow = DY_b + 2
        jog_pipe(L, [(PA[c], dist_south + 1), (PA[c], Wrow), (Sx[c] - 1, Wrow)], (1, 0))
        # BOT compute -> BOT store (straight down)
        L.pipe([(ocol, bot_c_south[c] + 1), (ocol, TS_b - 1)])
        # BOT store -> merger (straight down)
        L.pipe([(ocol, bstore_south + 1), (ocol, MG - 1)])
    # ---- O room ----
    L.output_room(o_col - 1, mg_south + 3)
    L.pipe([(o_col, mg_south + 1), (o_col, mg_south + 2)])
    L.save(path)
    print('FOOT', L.footprint())
    return L

if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'folded':
    build_folded('/private/tmp/claude-501/-Users-visenbaev-icfpc26/45d36e33-5a95-458c-9599-9b3faeeb9c09/scratchpad/ringfree_folded.man')
