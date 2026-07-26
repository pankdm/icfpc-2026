"""Place the v2 op-stream into a .man grid, with a floorplan built for a square box.

The stock `lllm_layout` floorplan puts a 31-column code band and two *straight*
belts (400 and 18 cells) in a column, which for the v2 op-stream comes out
149x505 -- box 255,025.  Two things fix that:

  * RESPACED ATTACHMENTS.  A pipe's column band inside a room is the Voronoi cell
    of its attachment among the attachments of the same direction, so clustering
    the cold services (input, display command, cells belt) at the west end hands
    the state belt every column east of them.  The code band goes from 31 columns
    to ~110, which is a straight division of the code's row count.
  * FOLDED BELTS.  A belt's length is its latency *and* its capacity, so it must
    be preserved cell-for-cell -- but not as a straight line.  Each belt is drawn
    as a vertical boustrophedon inside its own column strip: the 140-cell cells
    belt becomes 19 rows x 15 columns instead of 140 rows x 1, and because each
    strip is self-contained no two pipes ever cross.

  cd s4 && python3 solutions/little-little-little-man/build2_man.py out.man [--gw N]
"""
import argparse, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import lllm_layout as LL
import lllm_build2 as B
import driver16

# ---- column plan (west to east) -------------------------------------------
INP = 2             # input pipe (incoming, cold)
CMD = 5             # display command pipe (outgoing, cold)
COUT = 40           # cells belt out; its fold occupies COUT .. COUT+2*(n-1)
CIN = 58            # cells belt in
SOUT = 100          # state belt out
SIN = 110           # state belt in (its fold must not overlap SOUT's strip)


def vsnake(x0, ytop, ybot, nlegs, dx=2):
    """Waypoints of a vertical boustrophedon from (x0, ytop) going down first.

    `nlegs` must be odd so the walk ends on the bottom row.  A two-cell tail then
    drops clear of the boustrophedon before reaching the relay room: the oracle
    identifies a pipe's ends by the cell *beyond* them, so every down-leg that
    touched the relay room's wall would parse as a separate pipe endpoint.
    """
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


def relay_ring(p, x0, ytop, width, stations):
    """A 4-row room holding one relay man walking an `r s r s ...` ring."""
    p.room(x0, ytop, width, 4)
    r0, r1 = ytop + 1, ytop + 2
    p.put(x0 + 1, r0, '@')
    p.put(x0 + 2, r0, '>')
    c = x0 + 3
    end = x0 + 3 + 2 * stations
    while c + 1 <= end:
        p.put(c, r0, 'r'); p.put(c + 1, r0, 's'); c += 2
    p.put(c, r0, 'v'); p.put(c, r1, '<')
    c -= 1
    while c - 1 >= x0 + 3:
        p.put(c, r1, 'r'); p.put(c - 1, r1, 's'); c -= 2
    p.put(x0 + 2, r1, '^')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?', default=os.path.join(HERE, 'v2.man'))
    ap.add_argument('--gw', type=int, default=180, help='code room width')
    ap.add_argument('--cell-legs', type=int, default=7)
    ap.add_argument('--cell-h', type=int, default=20)
    ap.add_argument('--state-legs', type=int, default=3)
    ap.add_argument('--state-h', type=int, default=6)
    ap.add_argument('--cell-relay', type=int, default=6)
    ap.add_argument('--state-relay', type=int, default=3)
    args = ap.parse_args()

    GW = args.gw
    band_lo = max((COUT + SOUT) // 2, (CIN + SIN) // 2) + 1
    cells_lo = max((CMD + COUT) // 2, (INP + CIN) // 2) + 1
    cells_hi = min((COUT + SOUT) // 2, (CIN + SIN) // 2) - 1

    LL.INP = INP
    LL.CMD_C = CMD
    LL.SOUT_C, LL.SIN_C = SOUT, SIN
    LL.COUT_C, LL.CIN_C = COUT, CIN
    LL.CELLS_BAND = (cells_lo + 4, cells_hi)
    LL.STATE_BAND = (band_lo + 2, GW - 4)   # wrap() writes at BR+1, keep it interior
    LL.GATE_W = GW
    LL.TOP = 1

    def railcol(self):
        # loop back-edge rails: cold gaps that no pipe op or excursion touches
        if self.region == 'state':
            return band_lo - 8 + 2 * self.sdepth
        return cells_lo - 3 + 2 * self.cdepth
    LL.Lay.railcol = railcol

    def build_rooms(self):
        p = self.p
        # strict put: a silent overwrite is how two pipe folds merge into a
        # "pipe self-loop" load error that nothing else reveals.
        _put = p.put

        def put(x, y, ch, *a, **k):
            old = p.get(x, y)
            assert (old == ' ' or old == ch
                    or (old in '+-|=:' and ch in '+-|=:')), \
                f"floorplan overlap at {(x,y)}: {old!r} vs {ch!r}"
            _put(x, y, ch, *a, **k)
        p.put = put
        SOUTH = self.maxy + 3
        self.SOUTH = SOUTH
        p.room(0, 0, GW, SOUTH)

        # --- cells belt: two folds in their own column strips ---------------
        ct, cb = SOUTH, SOUTH + args.cell_h
        out_pts = vsnake(COUT, ct, cb, args.cell_legs)
        in_pts = vsnake(CIN, ct, cb, args.cell_legs)
        p.pipe(out_pts)
        p.pipe(list(reversed(in_pts)))
        relay_lo = min(out_pts[-1][0], in_pts[-1][0]) - 2
        relay_hi = max(out_pts[-1][0], in_pts[-1][0]) + 2
        relay_ring(p, relay_lo, cb + 3, relay_hi - relay_lo + 1, args.cell_relay)

        # --- state belt: same construction, much shorter --------------------
        st, sb = SOUTH, SOUTH + args.state_h
        so = vsnake(SOUT, st, sb, args.state_legs)
        si = vsnake(SIN, st, sb, args.state_legs)
        p.pipe(so)
        p.pipe(list(reversed(si)))
        rlo = min(so[-1][0], si[-1][0]) - 2
        rhi = max(so[-1][0], si[-1][0]) + 2
        relay_ring(p, rlo, sb + 3, rhi - rlo + 1, args.state_relay)

        # --- input room -----------------------------------------------------
        p.input_room(INP - 1, SOUTH + 3)
        p.pipe([(INP, SOUTH + 2), (INP, SOUTH)])

        # --- display driver, west, below the room ---------------------------
        dvx, dvy = 8, SOUTH + 5   # the SWAP pipe needs 3 rows above the driver room
        info = driver16.build_driver(p, dvx, dvy, None, 16, 16)
        rENTRY = info['rENTRY']
        DR = info['DR']
        p.pipe([(CMD, SOUTH), (CMD, rENTRY), (DR.x0 - 1, rENTRY)])
        self.cells_len = (path_len(out_pts), path_len(in_pts))
    LL.Lay.build_rooms = build_rooms

    ops = B.build()
    lay = LL.Lay()
    lay.use_display = True
    lay.spawn()
    lay.emit(ops)
    lay.save(args.out)
    fp = lay.p.footprint()
    w, h = (fp["w"], fp["h"]) if isinstance(fp, dict) else fp[:2]
    print(f"{args.out}  {w}x{h}  box {max(w,h)**2}  ops {B.flat(ops)}  "
          f"band {LL.STATE_BAND}  cells-belt {lay.cells_len} "
          f"(need {'>=256'})")


if __name__ == '__main__':
    main()
