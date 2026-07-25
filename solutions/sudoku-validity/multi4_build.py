"""Build solutions/sudoku-validity/multi2.man — SQUARER multi-man validator (Lever A).

Same op-streams as multi.man (controller/dispatcher/men/merger behaviour byte-identical)
but the 6 storage men are a VERTICAL STACK placed BESIDE the controller instead of a
38-wide horizontal band stacked BELOW it. Trades the height-71 strip for a squarer box.

Topology (controller + I-room + relay identical to multi.man, on the south wall):

  CONTROLLER (cols 0-15, rows 0-33) -- south-wall pipes --> I-room + relay (below)
        | dispatch pipe (col 10 south wall) routed east
        v
  DISPATCHER (vertical serpentine) --6 east pipes-->
     MEN (6x 2-row men, vertical stack) --6 east pipes-->
        MERGER (tall room) --south pipe--> O
"""
import sys, importlib.util
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from layout import Layout, DIRS

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m
ctrl = load('/Users/visenbaev/icfpc26/solutions/sudoku-validity/ctrl_v2.py', 'ctrl')
mb   = load('/Users/visenbaev/icfpc26/solutions/sudoku-validity/multi_build.py', 'mb')

place_controller = mb.place_controller
relay = mb.relay
vpipe = mb.vpipe


# ---------------------------------------------------------------------------
# LEVER B: confined-send controller. sS (feed) and rS (recv_any) go INLINE with no
# column glide, because the serpentine is confined to cols [1..XR] where F is always the
# nearest OUTGOING pipe. F and D sit on the SAME south wall, so nearest-of-two depends
# only on column (the row term cancels): XR < midpoint(F,D) => every inline cell has F
# nearest. Only rIN (col I, start-only) and the 6 sD (col D) stay disciplined; sD does a
# short east excursion. Killing the 22 sS wraps collapses the serpentine's rows and its
# loop-back riser -> big glide/tick cut.
# ---------------------------------------------------------------------------
def lay_controller2(prog, cols, W=15, XR=12):
    XL = 1
    I = cols['I']; F = cols['F']; D = cols['D']
    SMAX = 8                                  # sS may sit at any col <= SMAX (F still nearest vs D=10)
    assert SMAX < (F + D) / 2, f'SMAX={SMAX} must keep F={F} nearest vs D={D}'
    assert XL <= D <= XR, 'D must be INSIDE the serpentine so sD needs no excursion'
    RISER = W - 2
    cells = {}
    def put(x, y, g):
        if g == ' ':
            cells.setdefault((x, y), ' '); return
        if (x, y) in cells and cells[(x, y)] not in (' ', g):
            raise SystemExit(f'ctrl2 collision {(x,y)} {cells[(x,y)]} vs {g}')
        cells[(x, y)] = g
    put(XL, 1, '@'); put(XL+1, 1, 'v'); put(XL+1, 2, '>')
    st = {'x': XL+2, 'y': 2, 'd': 'E'}
    def adv():
        st['x'] += 1 if st['d'] == 'E' else -1
    def wrap():
        x, y, d = st['x'], st['y'], st['d']
        if d == 'E':
            while x < XR: put(x, y, ' '); x += 1
            put(XR, y, 'v'); y += 1; put(XR, y, '<'); x = XR-1; d = 'W'
        else:
            while x > XL: put(x, y, ' '); x -= 1
            put(XL, y, 'v'); y += 1; put(XL, y, '>'); x = XL+1; d = 'E'
        st['x'], st['y'], st['d'] = x, y, d
    def can_place():
        return (st['d'] == 'E' and st['x'] <= XR-1) or (st['d'] == 'W' and st['x'] >= XL+1)
    def route_to(T):
        g = 0
        while st['x'] != T:
            g += 1; assert g < 10000, 'route stuck'
            x, y, d = st['x'], st['y'], st['d']
            if d == 'E':
                if x < T and T <= XR-1: put(x, y, ' '); st['x'] += 1
                else: wrap()
            else:
                if x > T and T >= XL+1: put(x, y, ' '); st['x'] -= 1
                else: wrap()
    def place_at(T, g):                           # glide to column T, place, advance
        route_to(T)
        if not can_place():
            wrap(); route_to(T)
        put(st['x'], st['y'], g); adv()
    IMAX = 3                                      # rIN may sit at any col <= IMAX (I=2 nearest vs R=5)
    for op in prog:
        k = op if isinstance(op, str) else op[0]
        g = mb.glyph_of(op)
        if k == 'rIN':
            if not can_place():
                wrap()
            if st['x'] > IMAX or st['x'] < XL+1:
                place_at(min(IMAX, XR-1), g)      # glide left to the I-nearest region
            else:
                put(st['x'], st['y'], g); adv()
        elif k == 'sD':
            place_at(D, g)                        # dispatch: col D (inside serpentine, inline)
        elif k == 'sS':
            # feed: place INLINE if the cursor is already at a col where F is nearest
            # (<= SMAX); otherwise glide to SMAX. No wrap-to-exact-column-7.
            if not can_place():
                wrap()
            if st['x'] > SMAX:
                place_at(SMAX, g)
            else:
                put(st['x'], st['y'], g); adv()
        else:                                     # compute, rS(recv_any) -> inline, free
            if not can_place():
                wrap()
            put(st['x'], st['y'], g); adv()
    # loop-back riser (end -> down -> east to RISER -> up to row1 -> west to entry)
    endx, endy = st['x'], st['y']
    maxrow = max(yy for (_, yy) in cells)
    lane = maxrow + 1
    put(endx, endy, 'v')
    for yy in range(endy+1, lane): put(endx, yy, ' ')
    put(endx, lane, '>')
    for xx in range(endx+1, RISER): put(xx, lane, ' ')
    put(RISER, lane, '^')
    for yy in range(lane-1, 1, -1): put(RISER, yy, ' ')
    put(RISER, 1, '<')
    for xx in range(RISER-1, XL+1, -1): put(xx, 1, ' ')
    maxrow = max(yy for (_, yy) in cells)
    return dict(cells=cells, maxrow=maxrow, W=W)


def lay_controller3(prog, cols, W=14):
    """DOUBLE-serpentine controller (kills the long loop-back riser). The op-stream is
    split at the first sD: ops before it go DOWN the LEFT columns [1..6] (all sS land
    inline there, F=7 nearest), ops from the first sD onward go UP the RIGHT columns
    [7..12] (sD col 10 inline; sS glides to <=8). The two passes share the same rows, so
    the man returns to the top via the up-pass itself + a short top hop -- no 20-cell
    vertical riser. Column-disciplined ops: rIN (col<=3, start), sS (col<=8 => F), sD
    (col 10 => D). Op sequence byte-identical."""
    F = cols['F']; D = cols['D']; I = cols['I']
    SMAX, IMAX = 8, 3
    DXL, DXR = 1, 6                            # down-pass turn columns (left)
    UXL, UXR = 7, 12                           # up-pass turn columns (right)
    assert UXL <= D <= UXR
    SPLIT = next(i for i, op in enumerate(prog) if (op if isinstance(op, str) else op[0]) == 'sD')

    def mkput(cells):
        def put(x, y, g):
            if g == ' ':
                cells.setdefault((x, y), ' '); return
            if (x, y) in cells and cells[(x, y)] not in (' ', g):
                raise SystemExit(f'ctrl3 collision {(x,y)} {cells[(x,y)]} vs {g}')
            cells[(x, y)] = g
        return put

    def run(cells, ops, xl, xr, dyw, sx, sy, sd):
        """Place a serpentine of ops in cols [xl..xr]; dyw=+1 rows increase (down), dyw=-1
        rows decrease (man walks upward). Unified disciplined placement: rIN->col<=IMAX,
        sD->col D, sS->col<=SMAX, else inline. Returns end state {x,y,d}."""
        put = mkput(cells)
        turn = 'v' if dyw > 0 else '^'
        st = {'x': sx, 'y': sy, 'd': sd}
        def adv():
            st['x'] += 1 if st['d'] == 'E' else -1
        def wrap():
            x, y, d = st['x'], st['y'], st['d']
            if d == 'E':
                while x < xr: put(x, y, ' '); x += 1
                put(xr, y, turn); y += dyw; put(xr, y, '<'); x = xr-1; d = 'W'
            else:
                while x > xl: put(x, y, ' '); x -= 1
                put(xl, y, turn); y += dyw; put(xl, y, '>'); x = xl+1; d = 'E'
            st['x'], st['y'], st['d'] = x, y, d
        def can_place():
            return (st['d'] == 'E' and st['x'] <= xr-1) or (st['d'] == 'W' and st['x'] >= xl+1)
        def route_to(T):
            g = 0
            while st['x'] != T:
                g += 1; assert g < 10000, 'route stuck'
                x, d = st['x'], st['d']
                if d == 'E':
                    if x < T and T <= xr-1: put(x, st['y'], ' '); st['x'] += 1
                    else: wrap()
                else:
                    if x > T and T >= xl+1: put(x, st['y'], ' '); st['x'] -= 1
                    else: wrap()
        def place_at(T, g):
            route_to(T)
            if not can_place():
                wrap(); route_to(T)
            put(st['x'], st['y'], g); adv()
        for op in ops:
            k = op if isinstance(op, str) else op[0]
            g = mb.glyph_of(op)
            if k == 'rIN':
                if not can_place(): wrap()
                if not (xl+1 <= st['x'] <= IMAX):
                    place_at(min(IMAX, xr-1), g)
                else:
                    put(st['x'], st['y'], g); adv()
            elif k == 'sD':
                place_at(D, g)
            elif k == 'sS':
                if not can_place(): wrap()
                if st['x'] > SMAX:
                    place_at(SMAX, g)
                else:
                    put(st['x'], st['y'], g); adv()
            else:
                if not can_place(): wrap()
                put(st['x'], st['y'], g); adv()
        return st

    cells = {}
    put = mkput(cells)
    put(DXL, 1, '@'); put(DXL+1, 1, 'v'); put(DXL+1, 2, '>')
    # down pass (ops before the first sD)
    dend = run(cells, prog[:SPLIT], DXL, DXR, +1, DXL+2, 2, 'E')
    Ndmax = max(y for (_, y) in cells)
    # measure the up pass height by trial-placing it as a DOWN serpentine in a scratch
    scratch = {}
    run(scratch, prog[SPLIT:], UXL, UXR, +1, UXL+1, 2, 'E')
    Ru = max(y for (_, y) in scratch) - 2 + 1
    botrow = max(Ndmax, 1 + Ru) + 1
    # transition: down-pass end -> south to botrow -> east to UXL -> the man will head E
    dx, dy = dend['x'], dend['y']
    put(dx, dy, 'v')
    for yy in range(dy+1, botrow): put(dx, yy, ' ')
    put(dx, botrow, '>')
    for xx in range(dx+1, UXL): put(xx, botrow, ' ')
    # up pass starts at (UXL, botrow) heading E, walking upward (dyw=-1)
    uend = run(cells, prog[SPLIT:], UXL, UXR, -1, UXL, botrow, 'E')
    # loop-back: from up-pass end hop up to row 1 then WEST along the top to the entry
    ex, ey = uend['x'], uend['y']
    put(ex, ey, '^')
    for yy in range(ey-1, 1, -1): put(ex, yy, ' ')
    put(ex, 1, '<')
    for xx in range(ex-1, DXL+1, -1): put(xx, 1, ' ')
    maxrow = max(y for (_, y) in cells)
    return dict(cells=cells, maxrow=maxrow, W=W)


def place_controller3(L, prog, cols, W):
    lay = lay_controller3(prog, cols, W)
    Hroom = lay['maxrow'] + 2
    L.room(0, 0, W, Hroom)
    for (x, y), g in lay['cells'].items():
        if g == ' ':
            continue
        L.put(x, y, g)
    return Hroom


def place_controller2(L, prog, cols, W):
    lay = lay_controller2(prog, cols, W)
    Hroom = lay['maxrow'] + 2
    L.room(0, 0, W, Hroom)
    for (x, y), g in lay['cells'].items():
        if g == ' ':
            continue
        L.put(x, y, g)
    return Hroom


# ---------------------------------------------------------------------------
def vman(L, mx, my):
    """2-row storage man. Room 8 wide (cols mx..mx+7), 4 tall (rows my..my+3).
    Bit pipe enters the WEST wall (col mx); dup pipe exits the EAST wall (col mx+7).
    Op loop r & s r | M:
      rowA (my+1):  @  >  r  &  s  v
      rowB (my+2):     ^  M  |  r  <
    Returns pipe row (my+1)."""
    L.room(mx, my, 8, 4)
    a, b = my+1, my+2
    L.put(mx+1, a, '@'); L.put(mx+2, a, '>'); L.put(mx+3, a, 'r'); L.put(mx+4, a, '&'); L.put(mx+5, a, 's'); L.put(mx+6, a, 'v')
    L.put(mx+2, b, '^'); L.put(mx+3, b, 'M'); L.put(mx+4, b, '|'); L.put(mx+5, b, 'r'); L.put(mx+6, b, '<')
    return a


# ---------------------------------------------------------------------------
def dispatcher_v(L, dx, rows):
    """Vertical serpentine dispatcher. Room cols dx..dx+7 (8 wide), rows 0..(rows[-1]+3).
    Interior cols: SP=dx+1 (spawn + return riser), P=dx+2, o1=dx+3, o2=dx+4, o3=dx+5, Q=dx+6.
    Header row 1: @ spawns E into P='v' -> down col P into r0 entry '>'.
    Per man row rk: R (recv dispatch, recv_any) then s s (send twice EAST to man k);
    the two sends sit on row rk so 'send nearest' resolves by ROW to man k's east pipe.
    E-rows enter P='>' exit Q='v'; W-rows enter Q='<' exit P='v'. The return riser reuses
    the (otherwise-free) spawn column SP to loop the man from the bottom back to r0.
    dispatch pipe attaches the WEST wall (dx) — set by caller. Returns east_wall col."""
    SP, P, o1, o2, o3, Q = dx+1, dx+2, dx+3, dx+4, dx+5, dx+6
    top, bot = 0, rows[-1] + 3
    L.room(dx, top, 8, bot-top+1)
    r0 = rows[0]
    # header + riser re-entry both converge on r0 entry (P,r0)='>'
    L.put(SP, 1, '@'); L.put(P, 1, 'v')      # @ -> E -> v -> S down P into (P,r0)
    L.put(SP, r0, '>')                        # riser arrives up SP, turns E into (P,r0)
    for i, rk in enumerate(rows):
        if i % 2 == 0:                        # E-row
            L.put(P, rk, '>'); L.put(o1, rk, 'R'); L.put(o2, rk, 's'); L.put(o3, rk, 's'); L.put(Q, rk, 'v')
        else:                                 # W-row
            L.put(Q, rk, '<'); L.put(o3, rk, 'R'); L.put(o2, rk, 's'); L.put(o1, rk, 's'); L.put(P, rk, 'v')
    # loop-back from last row (W-row): P='v' -> gap row -> west to SP -> up SP to (SP,r0)='>'
    last = rows[-1]
    L.put(P, last+1, '<'); L.put(SP, last+1, '^')
    return dx+7                               # east wall col


# ---------------------------------------------------------------------------
def merger_v(L, gx, rows, o_pipe_row):
    """Tall merger room, cols gx..gx+5 (6 wide). Six dup pipes attach the WEST wall
    (col gx) at the man rows. Op-stream identical to multi.man's flat merger:
      R M (R|M)*4 R|  X   -> A==0: 1 s (loop) ;  A>0: 0 s H
    Laid as a down-column of the 16 OR-ops (R is recv_any -> position-free), then X, then
    the two branches (dup branch bends SOUTH to stay narrow). One outgoing pipe -> O.
    Interior cols gx+1..gx+4: dup s/H at gx+1, 0 & @ at gx+2, OR column OC=gx+3, riser gx+4.
    Returns south-wall O attach col."""
    OC = gx + 3                              # OR op column
    RIS = gx + 4                             # loop riser
    DB = gx + 1                              # dup-branch (s,H) column
    top = 0
    bot = max(rows[-1], 21) + 2
    L.room(gx, top, 6, bot-top+1)
    ops = ['R', 'M'] + ['R', '|', 'M'] * 4 + ['R', '|']   # 16 ops
    L.put(OC-1, 1, '@'); L.put(OC, 1, 'v')   # @ -> E -> v -> S down OR column
    L.put(RIS, 1, '<')                       # riser return -> W to (OC,1)
    y = 2
    for op in ops:
        L.put(OC, y, op); y += 1
    xrow = y                                 # X row
    L.put(OC, xrow, 'X')
    # ok branch (A==0, straight South): 1 s  then loop back up
    L.put(OC, xrow+1, '1'); L.put(OC, xrow+2, 's')
    L.put(OC, xrow+3, '>'); L.put(RIS, xrow+3, '^')      # east to riser, up to header '<'
    # dup branch (A>0, CW from South = West): 0, bend S, s, H
    L.put(OC-1, xrow, '0'); L.put(DB, xrow, 'v'); L.put(DB, xrow+1, 's'); L.put(DB, xrow+2, 'H')
    return OC                                # O attach column on south wall


# ---------------------------------------------------------------------------
def build_full2():
    prog = ctrl.build_dispatch()
    L = Layout()
    W = 15                                    # confined-send controller (cols 0-14)
    cols = dict(I=2, R=5, F=7, D=10)
    Hroom = place_controller3(L, prog, cols, W)
    sw = Hroom - 1                           # controller south wall row

    # --- I-room + relay: identical to multi.man (below the controller) ---
    iwall = sw + 4
    L.input_room(cols['I']-1, iwall); vpipe(L, cols['I'], iwall, sw)
    rwall = sw + 3
    L.room(4, rwall, 6, 4); relay(L, 5, rwall+1)
    vpipe(L, cols['F'], sw, rwall); vpipe(L, cols['R'], rwall, sw)

    # --- vertical apparatus to the RIGHT ---
    MY = 1
    rows = [MY + 4*k + 1 for k in range(6)]  # man pipe rows (pitch 4)

    DX = 16                                  # gap col 15 (dispatch pipe routes via the south, not this gap)
    disp_east = dispatcher_v(L, DX, rows)    # east wall col
    disp_south = rows[-1] + 3                 # dispatcher south wall row (matches dispatcher_v bot)

    MX = disp_east + 3                        # gap of 2 cols (disp_east+1, +2) -> pipe
    for k in range(6):
        vman(L, MX, MY + 4*k)
    man_east = MX + 7

    GX = man_east + 3                         # gap of 2 -> dup pipes
    o_col = merger_v(L, GX, rows, None)

    # --- wiring ---
    # dispatch pipe: controller south wall (D,sw) -> east along row sw+1 (clear of relay at
    # cols<=9) -> up into the dispatcher SOUTH wall from below. Enters at an interior col so
    # no bend sits adjacent to the controller east wall (avoids the spurious-attach gotcha).
    D = cols['D']
    entry_col = DX + 3                         # a dispatcher interior column
    # leave the south wall heading SOUTH, run along a lane BELOW both the controller and the
    # (now taller) dispatcher, then come UP into the dispatcher south wall from below.
    lane = max(sw, disp_south) + 2
    L.pipe([(D, sw+1), (D, lane), (entry_col, lane), (entry_col, disp_south+1)])

    # bit pipes: dispatcher east wall (disp_east,rk) -> man west wall (MX,rk)
    for rk in rows:
        L.pipe([(disp_east+1, rk), (MX-1, rk)])
    # dup pipes: man east wall (man_east,rk) -> merger west wall (GX,rk)
    for rk in rows:
        L.pipe([(man_east+1, rk), (GX-1, rk)])

    # output: merger south wall (o_col) -> O room below
    mg_bot = None
    # find merger south wall row from render bounds later; compute here:
    mg_south = max(rows[-1], 21) + 2         # merger bottom wall row (matches merger_v bot)
    owall = mg_south + 4
    L.output_room(o_col-1, owall)
    vpipe(L, o_col, mg_south, owall)

    print(L.render())
    print('FOOT', L.footprint())
    L.save('/Users/visenbaev/icfpc26/solutions/sudoku-validity/multi4.man')
    return L


if __name__ == '__main__':
    build_full2()
