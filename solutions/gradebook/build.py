import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'tools'))
import littleman as lm

# Grade Book machine.  Belt = circulating FIFO: ids(>=1000), grades(0..100),
# sentinel(-1).  ids and grades occupy disjoint ranges -> structure for free.
# Pipes on gate BOTTOM wall (column-addressed):
#   IN r@2   OUT s@5   R1 r@8 s@11   R2 r@14 s@17   R3 r@20 s@23   BELT r@26 s@29
# Per op: read op -> B; ALIGN (drain belt to sentinel, leaves it at student 0);
# dispatch on B; op reads its args then scans the aligned belt.

GW, GH = 39, 150
WALLY = GH
IN, OUT = 2, 5
R1I, R1O, R2I, R2O, R3I, R3O = 8, 11, 14, 17, 20, 23
R4I, R4O = 26, 29          # R4 holds the batch op-count O
BIN, BOUT = 31, 34
ARROW = {'E': '>', 'W': '<', 'N': '^', 'S': 'v'}
DXY = {'E': (1, 0), 'W': (-1, 0), 'N': (0, -1), 'S': (0, 1)}


class G:
    def __init__(self):
        self.p = lm.Program(); self.placed = {}
    def C(self, x, y, ch, gate=True):
        if gate and not (0 < x < GW - 1 and 0 < y < GH - 1):
            raise SystemExit(f"OUT OF ROOM {(x,y)} {ch!r}")
        if (x, y) in self.placed and self.placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x,y)}: {self.placed[(x,y)]!r} vs {ch!r}")
        self.placed[(x, y)] = ch; self.p.put(x, y, ch)


class Cur:
    def __init__(self, g, x, y, d):
        self.g, self.x, self.y, self.d = g, x, y, d
    def _s(self):
        dx, dy = DXY[self.d]; self.x += dx; self.y += dy
    def e(self, s):
        for ch in s:
            self.g.C(self.x, self.y, ch); self._s()
        return self
    def t(self, nd):
        self.g.C(self.x, self.y, ARROW[nd]); self.d = nd; self._s()
        return self
    def gto(self, col):
        assert self.d in ('E', 'W'), f"gto dir {self.d} at {(self.x,self.y)}"
        d = 1 if self.d == 'E' else -1
        assert (col - self.x) * d >= 0, f"gto({col}) wrong way d={self.d} at {(self.x,self.y)}"
        while self.x != col: self._s()
        return self
    def gy(self, row):
        assert self.d in ('N', 'S'), f"gy dir {self.d} at {(self.x,self.y)}"
        d = 1 if self.d == 'S' else -1
        assert (row - self.y) * d >= 0, f"gy({row}) wrong way d={self.d} at {(self.x,self.y)}"
        while self.y != row: self._s()
        return self
    def pos(self): return (self.x, self.y, self.d)


def relay(p, g, x0, y0):
    # 6-wide memory-style relay; man loops @ -> r -> v / < -> s -> . -> ^ -> > -> @
    p.man(x0 + 2, y0)
    g.C(x0 + 1, y0, '>', 0); g.C(x0 + 2, y0, '@', 0); g.C(x0 + 3, y0, 'r', 0); g.C(x0 + 4, y0, 'v', 0)
    g.C(x0 + 4, y0 + 1, '<', 0); g.C(x0 + 3, y0 + 1, 's', 0); g.C(x0 + 2, y0 + 1, '.', 0); g.C(x0 + 1, y0 + 1, '^', 0)


def build():
    g = G(); p = g.p
    p.room(0, 0, GW, GH)
    p.input_room(IN - 1, GH + 2); p.pipe([(IN, GH + 1), (IN, WALLY)])
    p.output_room(OUT - 1, GH + 2); p.pipe([(OUT, WALLY), (OUT, GH + 1)])
    for (ci, co) in [(R1I, R1O), (R2I, R2O), (R3I, R3O), (R4I, R4O)]:
        ry = GH + 2
        p.room(ci - 1, ry, (co - ci) + 3, 4); relay(p, g, ci - 1, ry + 1)
        p.pipe([(co, WALLY), (co, ry - 1)]); p.pipe([(ci, ry - 1), (ci, WALLY)])
    build_belt(g)
    p.man(1, 1)
    program(g)
    return g


def build_belt(g):
    p = g.p
    base = GH + 1; XS, XE = 37, 61
    wp = [(BOUT, WALLY), (BOUT, base), (XS, base)]
    y = base; goright = True; lastx = XS
    for _ in range(3):
        nx = XE if goright else XS
        wp.append((nx, y)); y += 1; wp.append((nx, y)); lastx = nx; goright = not goright
    ey = y
    if lastx != XE: wp.append((XE, ey)); lastx = XE
    wp.append((XE + 1, ey)); p.pipe(wp)
    rx = XE + 2; p.room(rx, ey - 1, 6, 4); relay(p, g, rx, ey)
    # return leaves the relay LEFT wall heading WEST (perpendicular), then up to BIN
    p.pipe([(rx - 1, ey + 1), (BIN, ey + 1), (BIN, WALLY)])


# --------------------------------------------------------------------------
# Helpers: feeder rows.  A block is an eastward action row started at col1 via
# a '>' feeder.  arrive_feeder(y) turns a west-heading cursor onto col1 then
# down into the feeder; enter(y) returns a cursor at (2,y) heading E.

def feeder(g, y):
    g.C(1, y, '>')
    return Cur(g, 2, y, 'E')


# ---- rails / routing discipline ----
#   col1  : feeder turn column ('>' at each block's entry row)
#   col31 : return rail (kept clear; op-ends ascend it)
#   row10 : return highway (kept clear; joins rail top to MAIN feeder)
HWY = 9
READO_Y = 11
OPCHK_Y = 14
PROC_Y = 18
READOP_Y = 21
ALIGN_Y = 24
DISPATCH_Y = 28
MIDX = 16          # clear middle column for compare/branch cells


def feeder(g, y):
    g.C(1, y, '>')
    return Cur(g, 2, y, 'E')


RET_CHAN = 36     # northbound channel: op-return -> OPCHK
O_CHAN = 37       # northbound channel: O==0 -> READO


def dn(g, cur, Y):
    """Forward/short jump: descend on cur's column to approach row Y-1 (clear),
    west to col1, single step into feeder (1,Y)."""
    cur.t('S').gy(Y - 1).t('W').gto(1).t('S')
    g.C(1, Y, '>')
    return Cur(g, 2, Y, 'E')


def rf(g, c, y):
    """Short down-jump used within an op (y should be c.y+2..+4)."""
    return dn(g, c, y)


def up_chan(g, cur, Y, chan, attr):
    """Backward jump: east to `chan`, north up to approach row Y-1, then (once)
    west to col1 and step into feeder (1,Y).  Subsequent callers merge in."""
    cur.gto(chan).t('N').gy(Y - 1)
    if not getattr(g, attr, False):
        cur.t('W').gto(1).t('S'); g.C(1, Y, '>'); setattr(g, attr, True)


def ret_main(g, c):
    up_chan(g, c, OPCHK_Y, RET_CHAN, 'ret_wired')       # op-return -> OPCHK


def belt_re(g, fy):
    """man at (2,fy) E: read belt@26, echo@29, route to (MIDX,fy+1) heading W."""
    c = Cur(g, 2, fy, 'E')
    c.gto(BIN).e('r').gto(BOUT).e('s')     # (26)r cell ; (29)s echo ; now (30,fy) E
    c.t('S').t('W').gto(MIDX)              # (30,fy)v (30,fy+1)< glide to (MIDX,fy+1) W
    return c                               # heading W at (MIDX,fy+1)


def _loop_W(g, xcx, fy):    # straight-W exit -> feeder (via own row fy+1, west part clear)
    Cur(g, xcx - 1, fy + 1, 'W').gto(1).t('N').gy(fy); g.C(1, fy, '>')

def _loop_N(g, xcx, fy):    # CW-N exit -> feeder (turn on clear row fy-1)
    Cur(g, xcx, fy, 'N').gy(fy - 1).t('W').gto(1).t('S').gy(fy); g.C(1, fy, '>')

def _loop_S(g, xcx, fy):    # CCW-S exit -> feeder (turn on clear row fy+2)
    Cur(g, xcx, fy + 2, 'S').t('W').gto(1).t('N').gy(fy); g.C(1, fy, '>')

def _start(g, xcx, fy, d):
    return {'W': Cur(g, xcx - 1, fy + 1, 'W'),
            'N': Cur(g, xcx, fy, 'N'),
            'S': Cur(g, xcx, fy + 2, 'S')}[d]

def wire_x(g, xcx, fy, special):
    """X at (xcx,fy+1) heading W.  Two of {W,N,S} loop back to feeder (1,fy);
    the `special` one is returned as a live cursor for the caller to route."""
    for d, mk in (('W', _loop_W), ('N', _loop_N), ('S', _loop_S)):
        if d != special:
            mk(g, xcx, fy)
    return _start(g, xcx, fy, special)

def wire_d(g, dcx, fy):
    """d at (dcx,fy+1) heading W.  BP>0 -> CW-N loops back; BP==0 -> straight-W special."""
    _loop_N(g, dcx, fy)
    return _start(g, dcx, fy, 'W')


def program(g):
    # ================= ROSTER =================
    c = Cur(g, 2, 1, 'E')
    c.e('rM')                 # r A=N ; M B=N
    c.t('S').t('W').gto(2).e('r')   # (4,1)v (4,2)< ... (2,2)r A=K
    c.t('S').t('E')           # (1,2)v (1,3)>
    c.e('*+b')                # * A=K*N ; + A=total ; b BP=total
    c.t('S').t('W').gto(1).t('S').t('E')   # (5,3)v (5,4)< ...(1,4)v (1,5)>
    # LOAD-LOOP entry (2,5) E ; feeder (1,5) already placed
    g.C(1, 5, '>')
    c.e('r')                  # (2,5) r A=val
    c.gto(BOUT).e('s')        # send val to belt
    c.t('S').t('W').gto(MIDX)  # route to (MIDX,6) heading W
    c.e('m').e('d')           # m BP-- ; d BP>0 CW(N) loop ; ==0 straight(W) exit
    ex = wire_d(g, MIDX - 1, 5)   # loop back to (1,5) ; ex = straight-W (exit) cursor
    # exit: push sentinel -1 to belt, then READ_O
    ex.e('1N')                # A=1 ; N A=-1
    ex.t('S').t('E').gto(BOUT).e('s')   # send -1 to belt
    read_o(g, dn(g, ex, READO_Y))


def read_o(g, c):
    # (2,READO_Y) E : read batch count O -> R4 ; fall through to OPCHK.
    c.e('r').gto(R4O).e('s')             # r A=O ; s -> R4
    opchk(g, dn(g, c, OPCHK_Y))


def opchk(g, c):
    # (2,OPCHK_Y) E : read O from R4 ; O==0 -> next round ; O>0 -> dec & process.
    c.gto(R4I).e('r')                    # r A=O (consumes R4) ; at (R4I+1,OPCHK_Y)
    c.t('S').t('W').gto(MIDX)            # route to (MIDX,OPCHK_Y+1) heading W
    c.e('N').e('X')                      # N A=-O ; X heading W at (MIDX-1,OPCHK_Y+1)
    xcx, fy = MIDX - 1, OPCHK_Y + 1
    # X on A=-O: O>0 -> A<0 -> CCW-S = process(down) ; O==0 -> straight-W = READO ; (N unused)
    # straight-W (O==0): head E toward O_CHAN, up to READO
    z = Cur(g, xcx - 1, fy, 'W')
    z.t('S').t('E')
    up_chan(g, z, READO_Y, O_CHAN, 'o_wired')
    # CCW-S (O>0): down to PROC ; A=-O
    p = Cur(g, xcx, fy + 1, 'S')
    proc(g, dn(g, p, PROC_Y))


def proc(g, c):
    # (2,PROC_Y) E : A=-O.  write O-1 to R4 ; read op -> B ; ALIGN ; dispatch.
    c.e('NM1-N').gto(R4O).e('s')         # N A=O ; M B=O ;1 A=1 ;- A=1-O ;N A=O-1 ; s->R4
    d2 = dn(g, c, READOP_Y)
    d2.e('rM')                           # r A=op ; M B=op
    align(g, dn(g, d2, ALIGN_Y))


def align(g, c):
    # (2,ALIGN_Y) E : drain belt to sentinel (preserves B=op) ; then dispatch.
    cc = belt_re(g, ALIGN_Y)             # W at (MIDX,ALIGN_Y+1), A=cell
    cc.e('X')                            # ==0 W & >0 N = loop ; <0 S = exit(sentinel)
    ex = wire_x(g, MIDX, ALIGN_Y, 'S')
    dispatch(g, dn(g, ex, DISPATCH_Y))


DCOL = 30          # dispatch chain column (kept clear of glyphs by op code)
TESTS = [(30, 'get_op'), (54, 'set_op'), (78, 'avg_op'), (102, 'top_op')]


def dispatch(g, c):
    # c heading E at (2,DISPATCH_Y).  B=op.  linear test chain on DCOL.
    c.gto(DCOL).t('S').gy(TESTS[0][0])       # onto DCOL, descend to first test entry
    fns = {'get_op': get_op, 'set_op': set_op, 'avg_op': avg_op, 'top_op': top_op}
    for i, (TR, name) in enumerate(TESTS):
        k = i + 1
        g.C(DCOL, TR, '<')                   # entry: any arrival turns W into the test
        Cur(g, DCOL - 1, TR, 'W').e(str(k)).e('-').e('X')   # A=k-op ; X heading W
        # X at (DCOL-3,TR): match straight-W ; nomatch CCW-S (op>k)
        m = Cur(g, DCOL - 4, TR, 'W')        # match cursor
        fy = TR + 2
        m.gto(1).t('S').gy(fy); g.C(1, fy, '>')
        fns[name](g, Cur(g, 2, fy, 'E'))
        # nomatch -> back to DCOL, descend to next test
        nm = Cur(g, DCOL - 3, TR + 1, 'S')
        if i < len(TESTS) - 1:
            nm.t('E').gto(DCOL).t('S').gy(TESTS[i + 1][0])   # descend to next test entry
        else:
            nm.e('H')                        # op4 nomatch impossible; halt guard


def get_op(g, c):
    # aligned belt at student0.  read id -> B(target); read s -> R1.
    c = rf(g, c, c.y + 2); c.e('rM')                # r A=id ; M B=id(target)
    c = rf(g, c, c.y + 2); c.e('r').gto(R1O).e('s') # r A=s ; s -> R1
    # ---- SCAN: find belt cell == target ----
    sy = c.y + 2
    rf(g, c, sy)
    cc = belt_re(g, sy)                              # W at (MIDX,sy+1), A=cell
    cc.e('-').e('X')                                 # - A=cell-target ; X heading W ; ==0 W=MATCH
    m = wire_x(g, MIDX - 1, sy, 'W')                 # match cursor (W) ; N,S loop back
    gy = sy + 6
    # descend a clear column (avoid scan loop-back glyphs on col1) then into grab feeder
    m.gto(MIDX - 3).t('S').gy(gy - 1).t('W').gto(1).t('S'); g.C(1, gy, '>')
    grab(g, Cur(g, 2, gy, 'E'))


def grab(g, c):
    # read s from R1 (r@R1I=8) -> BP=s ; loop: read grade, echo, m, d.
    c.gto(R1I).e('r').e('b')                          # r A=s ; b BP=s
    ly = c.y + 2
    c = rf(g, c, ly)
    cc = belt_re(g, ly)                               # W at (MIDX,ly+1), A=grade
    cc.e('m').e('d')                                  # m BP-- ; d BP>0 CW(N) loop ; ==0 W=OUTPUT
    o = wire_d(g, MIDX - 1, ly)                        # output cursor (W), A=grade
    o.gto(OUT).e('s')                                 # s -> OUT@5
    o.t('S').t('E')                                   # turn to head E for return rail
    ret_main(g, o)


def belt_r(g, fy):
    """Read belt@BIN (NO echo), route to (MIDX,fy+1) heading W with A=cell."""
    c = Cur(g, 2, fy, 'E')
    c.gto(BIN).e('r')
    c.t('S').t('W').gto(MIDX)
    return c


# ============================= SET =============================
def set_op(g, c):
    c = rf(g, c, c.y + 2); c.e('rM')                 # id -> B(target)
    c = rf(g, c, c.y + 2); c.e('r').gto(R1O).e('s')  # s -> R1
    c = rf(g, c, c.y + 2); c.e('r').gto(R2O).e('s')  # v -> R2
    sy = c.y + 2
    rf(g, c, sy)
    cc = belt_re(g, sy); cc.e('-').e('X')            # scan for target (echoes)
    m = wire_x(g, MIDX - 1, sy, 'W')
    gy = sy + 6
    m.gto(MIDX - 3).t('S').gy(gy - 1).t('W').gto(1).t('S'); g.C(1, gy, '>')
    set_grab(g, Cur(g, 2, gy, 'E'))


def set_grab(g, c):
    c.gto(R1I).e('r').e('b')                          # BP = s
    ly = c.y + 4
    rf(g, c, ly)
    cc = belt_r(g, ly)                                # A=grade (no echo) at (MIDX,ly+1) W
    cc.e('m').e('d')                                  # m BP-- ; d at (MIDX-1,ly+1)
    # d>0 (CW-N): echo grade & loop ; d==0 (W): replace with v & ret
    en = Cur(g, MIDX - 1, ly, 'N')
    en.gy(ly - 1).t('E').gto(BOUT).e('s')             # send grade @BOUT (row ly-1)
    en.t('N').t('W').gto(1).t('S').gy(ly)             # loop back to feeder(ly)
    g.C(1, ly, '>')
    rv = Cur(g, MIDX - 2, ly + 1, 'W')                # d==0 straight-W (s-th grade)
    rv.gto(R2I).e('r')                                # A = v (from R2)
    rv.t('S').t('E').gto(BOUT).e('s')                 # send v @BOUT
    rv.t('S').t('E')
    ret_main(g, rv)


def avg_op(g, c):
    # STUB: read s arg (discard) and return to OPCHK (keeps input stream aligned)
    c = rf(g, c, c.y + 2); c.e('r')
    c.t('S').t('E')
    ret_main(g, c)

def top_op(g, c):
    # STUB: read s arg (discard) and return to OPCHK (keeps input stream aligned)
    c = rf(g, c, c.y + 2); c.e('r')
    c.t('S').t('E')
    ret_main(g, c)

if __name__ == '__main__':
    g = build()
    print(g.p.render())
    print('footprint', g.p.footprint())
