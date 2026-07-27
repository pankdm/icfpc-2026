"""LLLM v3 floorplan: dense band-boustrophedon placement, no pipe excursions.

v2 (`build2_man.py`) placed the op stream in a *home band* and jogged out to a
pipe column whenever an op belonged to another region -- three rows per jog.
On the v2 op stream that costs 160 code rows for 4,589 ops in a 125-column
band, where the ops themselves need 37.  The rest is excursion and newline tax.

v3 replaces the placer with the `boustro`/`railflow` model, which the snake and
pathfinder rebuilds already proved on this repo:

  * NEAREST-PIPE BANDS instead of regions.  Every pipe attaches to the same
    (bottom) wall of the code room, so nearest-pipe binding is pure column
    Voronoi.  Cluster all six ports in twelve columns at the WEST end and the
    state belt -- 77% of all emitted ops -- owns every column east of them.  An
    excursion becomes an ordinary `place`, i.e. zero extra rows.

  * ONE-ROW NEWLINE.  Boustrophedon rows alternate direction, so a wrap costs
    one row and no backtrack walk (v2's `newline` cost two rows plus a full-width
    walk back to the band's west edge).

  * RAIL BACK-EDGES.  A loop's back-edge is a column west of the op area: the
    body's last row runs west into it and `^` carries the man up to the head
    row's `>`.  Entry costs at most one row, the `d`/`X` tail two.  Rails are
    indexed by nesting depth, so an inner loop's rail is always east of its
    parent's and the westward man stops at his own.

  * FAN-OUT ROUTING.  The six pipes leave the wall in twelve adjacent columns
    and spread to their real targets in a band of six rows below the room, the
    easternmost port turning first.  With targets in the same left-to-right
    order as the ports, no two pipes can cross.

  cd s4 && python3 solutions/little-little-little-man/build3_man.py out.man --gw 120
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import littleman as lm            # noqa: E402
import lllm_build2 as B           # noqa: E402
import driver16                   # noqa: E402

E, W = 1, -1

# ---- port columns inside the code room (west to east) ----------------------
# Gaps of 3 keep every Voronoi boundary off a tie, so nearest-pipe binding never
# depends on the loader's reading-order tie-break.
PORTGLYPH = {'INP': 'r', 'CIN': 'r', 'SIN': 'r',
             'CMD': 's', 'COUT': 's', 'SOUT': 's'}
# Ports are SPREAD, not clustered.  Two facts force it:
#   * the state ring holds only 20 values, so its two pipes are latency-bound --
#     a fan-out that ran them 100 columns sideways cost 5.5x in ticks (measured:
#     543k -> 2.98M).  Every component therefore sits directly below its port.
#   * a port whose Voronoi band ABUTS the state band is nearly free, because the
#     man reaches it without a newline; one that does not costs ~1.6 rows.  So
#     `cmd` (20 static, the commonest cold op) and `rc` get the abutting bands
#     and `sc`/`ri` take the far ones.
DEFAULT_PORTS = {'INP': 2, 'COUT': 6, 'CIN': 16, 'CMD': 31,
                 'SOUT': 64, 'SIN': 69}
OPPORT = {'ri': 'INP', 'rc': 'CIN', 'r': 'SIN',
          'cmd': 'CMD', 'sc': 'COUT', 's': 'SOUT'}
OPMIN = 6
MAXDEPTH = 4                      # rails live in columns 1..MAXDEPTH


def voronoi(sites):
    sites = sorted(sites, key=lambda kv: kv[1])
    out = {}
    for i, (name, col) in enumerate(sites):
        lo = 1 if i == 0 else (sites[i - 1][1] + col) // 2 + 1
        hi = 10 ** 9 if i == len(sites) - 1 else (col + sites[i + 1][1]) // 2
        out[name] = (lo, hi)
    return out


class Lay3:
    """Band boustrophedon with rail back-edges."""

    def __init__(self, p, opmax, portcol, y0=0):
        self.p = p
        self.opmin, self.opmax = OPMIN, opmax
        self.portcol = portcol
        self.bands = {}
        for glyph in ('r', 's'):
            self.bands.update(voronoi([(n, c) for n, c in portcol.items()
                                       if PORTGLYPH[n] == glyph]))
        self.nl = 0
        self.nl_by = {}
        self.tag = '?'
        self.y0 = y0
        self.x, self.y, self.d = self.opmin - 1, y0 + 1, E
        self.depth = 0
        self.maxy = self.y
        self.intent = {}

    # --- primitives --------------------------------------------------------
    def put(self, x, y, ch):
        old = self.p.get(x, y)
        assert old == ' ', f"code overlap at {(x, y)}: {old!r} vs {ch!r}"
        self.p.put(x, y, ch)
        if y > self.maxy:
            self.maxy = y

    def newline(self):
        self.nl += 1
        self.nl_by[self.tag] = self.nl_by.get(self.tag, 0) + 1
        tx = self.x + self.d
        self.put(tx, self.y, 'v')
        self.put(tx, self.y + 1, '<' if self.d == E else '>')
        self.d = -self.d
        self.x, self.y = tx, self.y + 1

    def place(self, ch, lo=1, hi=10 ** 9):
        lo = max(lo, self.opmin)
        hi = min(hi, self.opmax)
        assert lo <= hi, (ch, lo, hi)
        for _ in range(4):
            if self.d == E:
                nx = max(self.x + 1, lo)
                if nx <= hi:
                    break
            else:
                nx = min(self.x - 1, hi)
                if nx >= lo:
                    break
            self.newline()
        else:
            raise RuntimeError(f"cannot place {ch!r} in [{lo},{hi}]")
        self.put(nx, self.y, ch)
        self.x = nx

    # --- loops -------------------------------------------------------------
    def _enter(self, rail):
        """Fall into a fresh eastbound head row through the rail column."""
        if self.d == E:
            self.newline()
        self.put(rail, self.y, 'v')
        head = self.y + 1
        self.put(rail, head, '>')
        self.x, self.y, self.d = self.opmin - 1, head, E
        return head

    def _tail_branch(self, glyph, rail, head):
        """`d`/`X` entered heading SOUTH: turn-west = back-edge, straight = exit."""
        tx = self.x + self.d
        self.put(tx, self.y, 'v')
        dy = self.y + 1
        self.put(tx, dy, glyph)
        self.put(rail, dy, '^')
        self.put(tx, dy + 1, '<')
        self.x, self.y, self.d = tx, dy + 1, W

    def _tail_go(self, rail, head):
        if self.d == E:
            self.newline()
        self.put(rail, self.y, '^')

    def emit_loop(self, tag, body):
        if tag == 'BPLOOP':
            self.place('b')
        self.depth += 1
        assert self.depth <= MAXDEPTH, self.depth
        rail = self.depth
        head = self._enter(rail)
        self.emit(body)
        if tag == 'BPLOOP':
            self.place('m')
            self._tail_branch('d', rail, head)
        elif tag == 'LOOPX':
            self._tail_branch('X', rail, head)
        elif tag == 'FOREVER':
            self._tail_go(rail, head)
        else:
            raise ValueError(tag)
        self.depth -= 1

    # --- driver ------------------------------------------------------------
    def emit(self, ops):
        for op in ops:
            if isinstance(op, tuple):
                if op[0] == '#':
                    assert 0 <= op[1] <= 9, op
                    self.place(str(op[1]))
                else:
                    self.emit_loop(op[0], op[1])
            elif op in OPPORT:
                port = OPPORT[op]
                lo, hi = self.bands[port]
                self.tag = op
                self.place(PORTGLYPH[port], lo, hi)
                self.tag = '?'
                self.intent[(self.x, self.y)] = port
            else:
                self.place(op)

    def spawn(self):
        self.put(self.opmin - 1, self.y, '@')


# ---------------------------------------------------------------- floorplan
def vsnake(x0, ytop, ybot, nlegs, dx=2):
    assert nlegs % 2 == 1, nlegs
    pts = [(x0, ytop)]
    x = x0
    down = True
    for i in range(nlegs):
        y = ybot if down else ytop + 1
        pts.append((x, y))
        if i < nlegs - 1:
            x += dx
            pts.append((x, y))
        down = not down
    pts.append((x, ybot + 2))
    return pts


def path_len(pts):
    n = 1
    for i in range(len(pts) - 1):
        n += abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
    return n


def relay_ring(p, x0, ytop, width, stations, grow='east', limit=None):
    """`grow='west'` widens the room leftwards, so it cannot swallow a column a
    deeper pipe still has to descend through."""
    need = max(width, 2 * stations + 8)
    if grow == 'west':
        x0 = max(0, x0 + width - need)
    width = need
    if limit is not None:
        assert x0 + width - 1 <= limit, \
            f"relay room {x0}..{x0 + width - 1} runs past {limit}"
    p.room(x0, ytop, width, 4)
    c0 = x0 + 2
    cE = c0 + 2 * stations + 1
    y = ytop + 1
    p.put(x0 + 1, y, '@')
    p.put(c0, y, '>')
    c = c0 + 1
    while c + 1 <= cE:
        p.put(c, y, 'r')
        p.put(c + 1, y, 's')
        c += 2
    p.put(cE + 1, y, 'v')
    p.put(cE + 1, y + 1, '<')
    c = cE
    while c - 1 >= c0 + 1:
        p.put(c, y + 1, 'r')
        p.put(c - 1, y + 1, 's')
        c -= 2
    p.put(c0, y + 1, '^')
    return x0 + width - 1


def solve_turn_rows(portcol, target, south):
    """Assign each pipe a fan-out row so that no two of the six pipes cross.

    Pipe i runs down column ``C_i`` to row ``R_i``, across to ``T_i``, then down.
    For two pipes with ``R_i < R_j`` the only possible crossings are j's upper
    leg through i's horizontal (``C_j`` inside i's span) and i's lower leg
    through j's horizontal (``T_i`` inside j's span), so a permutation is legal
    iff neither holds for every ordered pair.
    """
    import itertools
    names = list(portcol)

    def span(n):
        a, b = portcol[n], target[n]
        return (min(a, b), max(a, b))

    for perm in itertools.permutations(names):
        ok = True
        for a in range(len(perm)):
            for b in range(a + 1, len(perm)):
                i, j = perm[a], perm[b]
                lo, hi = span(i)
                if lo <= portcol[j] <= hi:
                    ok = False
                    break
                lo2, hi2 = span(j)
                if lo2 <= target[i] <= hi2:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return {n: south + 1 + k for k, n in enumerate(perm)}
    raise RuntimeError("no non-crossing fan-out order exists")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?', default=os.path.join(HERE, 'v3.man'))
    ap.add_argument('--gw', type=int, default=120)
    ap.add_argument('--split', type=int, default=1)
    ap.add_argument('--cell-legs', type=int, default=7)
    ap.add_argument('--cell-h', type=int, default=22)
    ap.add_argument('--cell-relay', type=int, default=8)
    ap.add_argument('--state-h', type=int, default=10)
    ap.add_argument('--state-relay', type=int, default=8)
    ap.add_argument('--drv-h', type=int, default=26)
    ap.add_argument('--drv-entry', type=int, default=13)
    ap.add_argument('--drv-gap', type=int, default=30)
    for name in DEFAULT_PORTS:
        ap.add_argument('--p' + name.lower(), type=int, default=None)
    ap.add_argument('--dvx', type=int, default=None)
    args = ap.parse_args()

    p = lm.Program()
    _put = p.put

    def strict_put(x, y, ch, *a, **k):
        old = p.get(x, y)
        assert (old == ' ' or old == ch
                or (old in '+-|=:' and ch in '+-|=:')), \
            f"floorplan overlap at {(x, y)}: {old!r} vs {ch!r}"
        _put(x, y, ch, *a, **k)
    p.put = strict_put

    opmax = args.gw - 3
    portcol = dict(DEFAULT_PORTS)
    for name in portcol:
        v = getattr(args, 'p' + name.lower())
        if v is not None:
            portcol[name] = v
    lay = Lay3(p, opmax, portcol)
    lay.spawn()
    ops = B.build()
    lay.emit(ops)

    SOUTH = lay.maxy + 3
    p.room(0, 0, args.gw, SOUTH)

    # --- input room (directly under INP) ----------------------------------
    p.input_room(portcol['INP'] - 1, SOUTH + 2)
    p.pipe([(portcol['INP'], SOUTH + 1), (portcol['INP'], SOUTH)])

    # --- cells belt (folds hang straight off COUT and CIN) ----------------
    cb = SOUTH + args.cell_h
    out_pts = vsnake(portcol['COUT'], SOUTH, cb, args.cell_legs)
    in_pts = vsnake(portcol['CIN'], SOUTH, cb, args.cell_legs)
    assert abs(portcol['COUT'] - portcol['CIN']) >= 2 * args.cell_legs, \
        "the two cells-belt folds overlap"
    p.pipe(out_pts)
    p.pipe(list(reversed(in_pts)))
    rlo = min(out_pts[-1][0], in_pts[-1][0]) - 2
    rhi = max(out_pts[-1][0], in_pts[-1][0]) + 2
    # grow WEST: the cmd pipe descends east of this room and must stay clear
    cells_east = relay_ring(p, rlo, cb + 3, rhi - rlo + 1, args.cell_relay,
                            grow='west', limit=portcol['CMD'] - 2)

    # --- state belt (straight, short: the ring is latency-bound) ----------
    sb = SOUTH + args.state_h
    sout_pts = vsnake(portcol['SOUT'], SOUTH, sb, 1)
    sin_pts = vsnake(portcol['SIN'], SOUTH, sb, 1)
    p.pipe(sout_pts)
    p.pipe(list(reversed(sin_pts)))
    slo = min(sout_pts[-1][0], sin_pts[-1][0]) - 2
    shi = max(sout_pts[-1][0], sin_pts[-1][0]) + 2
    state_east = relay_ring(p, slo, sb + 3, shi - slo + 1, args.state_relay)

    # --- display driver ---------------------------------------------------
    dvx = args.dvx if args.dvx is not None else portcol['CMD'] + 3
    # dvy >= SOUTH+3: the SWAP pipe bulges three rows ABOVE the driver room and
    # would otherwise be drawn inside the code room.
    info = driver16.build_driver(p, dvx, SOUTH + 4, None, 16, 16,
                                 room_h=args.drv_h, entry_off=args.drv_entry,
                                 disp_gap=args.drv_gap)
    rENTRY = info['rENTRY']
    DR = info['DR']
    assert DR.x0 > portcol['CMD'], "driver room west of its cmd pipe"
    assert dvx + 26 < portcol['SOUT'] - 2, "driver block reaches the state belt"
    p.pipe([(portcol['CMD'], SOUTH), (portcol['CMD'], rENTRY),
            (DR.x0 - 1, rENTRY)])

    p.put = _put
    p.save(args.out)
    fp = p.footprint()
    w, h = (fp['w'], fp['h']) if isinstance(fp, dict) else fp[:2]
    print(f"{args.out}  {w}x{h}  box {max(w, h) ** 2}  ops {B.flat(ops)}  "
          f"code-rows {lay.maxy}  newlines {lay.nl} {sorted(lay.nl_by.items(), key=lambda kv: -kv[1])}  SOUTH {SOUTH}  "
          f"cells-belt {path_len(out_pts) + path_len(in_pts)} (need >=270)  "
          f"state-belt {path_len(sout_pts) + path_len(sin_pts)}  "
          f"east cells {cells_east} state {state_east}")


if __name__ == '__main__':
    main()
