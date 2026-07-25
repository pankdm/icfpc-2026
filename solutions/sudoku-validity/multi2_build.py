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
ctrl = load('/Users/visenbaev/icfpc26/solutions/sudoku-validity/ctrl_onering.py', 'ctrl')
mb   = load('/Users/visenbaev/icfpc26/solutions/sudoku-validity/multi_build.py', 'mb')

place_controller = mb.place_controller
relay = mb.relay
vpipe = mb.vpipe


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
    """Tall merger room, cols gx..gx+6 (7 wide). Six dup pipes attach the WEST wall
    (col gx) at the man rows. Op-stream identical to multi.man's flat merger:
      R M (R|M)*4 R|  X   -> A==0: 1 s (loop) ;  A>0: 0 s H
    Laid as a down-column of the 16 OR-ops (R is recv_any -> position-free), then X, then
    the two branches. One outgoing pipe -> O (send nearest resolves to it).
    Interior cols: dcol=gx+1..gx+5. OR column = OC=gx+4; dup branch runs WEST from X;
    ok branch runs SOUTH; riser at OC+1. Returns south-wall O attach col."""
    OC = gx + 4                              # OR op column
    RIS = gx + 5                             # loop riser
    top = 0
    bot = max(rows[-1], 21) + 2
    L.room(gx, top, 7, bot-top+1)
    ops = ['R', 'M'] + ['R', '|', 'M'] * 4 + ['R', '|']   # 16 ops
    # entry: @ feeds v at (OC,1); down the OR column
    L.put(OC-1, 1, '@'); L.put(OC, 1, 'v')
    L.put(RIS, 1, '<')                       # riser return -> W to (OC,1)
    y = 2
    for op in ops:
        L.put(OC, y, op); y += 1
    xrow = y                                 # X row
    L.put(OC, xrow, 'X')
    # ok branch (A==0, straight South): 1 s  then loop back up
    L.put(OC, xrow+1, '1'); L.put(OC, xrow+2, 's')
    L.put(OC, xrow+3, '>'); L.put(RIS, xrow+3, '^')      # east to riser, up to header '<'
    # dup branch (A>0, CW from South = West): 0 s H
    L.put(OC-1, xrow, '0'); L.put(OC-2, xrow, 's'); L.put(OC-3, xrow, 'H')
    # output pipe attaches the SOUTH wall under OC (single outgoing -> both s reach it)
    return OC                                # O attach column on south wall


# ---------------------------------------------------------------------------
def build_full2():
    prog = ctrl.build_dispatch()
    L = Layout()
    W = 16
    cols = dict(I=2, R=5, F=7, D=10)
    Hroom = place_controller(L, prog, cols, W)
    sw = Hroom - 1                           # controller south wall row (33)

    # --- I-room + relay: identical to multi.man (below the controller) ---
    iwall = sw + 4
    L.input_room(cols['I']-1, iwall); vpipe(L, cols['I'], iwall, sw)
    rwall = sw + 3
    L.room(4, rwall, 6, 4); relay(L, 5, rwall+1)
    vpipe(L, cols['F'], sw, rwall); vpipe(L, cols['R'], rwall, sw)

    # --- vertical apparatus to the RIGHT ---
    MY = 1
    rows = [MY + 5*k + 1 for k in range(6)]  # man pipe rows: 2,7,12,17,22,27

    DX = 19                                  # gap cols 16,17,18 between controller(0-15) and dispatcher
    disp_east = dispatcher_v(L, DX, rows)    # east wall col

    MX = disp_east + 3                        # gap of 2 cols (disp_east+1, +2) -> pipe
    for k in range(6):
        vman(L, MX, MY + 5*k)
    man_east = MX + 7

    GX = man_east + 3                         # gap of 2 -> dup pipes
    o_col = merger_v(L, GX, rows, None)

    # --- wiring ---
    # dispatch pipe: controller south wall (D,sw) -> down, east, up to dispatcher WEST wall
    D = cols['D']
    disp_in_row = 14
    # route: (D,sw+1) south to a lane, east under I/relay to col DX-1, up to disp_in_row, into west wall
    lane = rwall + 5                          # a clear lane row below everything on the left
    # Route up the MIDDLE of the 3-wide gap (col DX-2), >=2 cols off both walls, so the
    # bend into the dispatcher does NOT spuriously attach to the controller east wall.
    midcol = DX - 2                           # 17: 2 off controller wall(15) and 2 off dispatcher wall(19)
    L.pipe([(D, sw+1), (D, lane), (midcol, lane), (midcol, disp_in_row), (DX-1, disp_in_row)])

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
    L.save('/Users/visenbaev/icfpc26/solutions/sudoku-validity/multi2.man')
    return L


if __name__ == '__main__':
    build_full2()
