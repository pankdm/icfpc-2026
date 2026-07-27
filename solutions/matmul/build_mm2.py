import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'tools'))
from mm2lib import RGrid                      # noqa: E402
from mm2route import route_long               # noqa: E402
import mm2rooms as R                          # noqa: E402
import router as RT                           # noqa: E402

# the router's default A* box (margin 6 around the two endpoints) is far too tight
# for nets that must detour around a 40-cell serpentine; widen it.
_ROUTE_PIPE = RT.route_pipe
RT.route_pipe = lambda grid, net, extra_cost=None, margin=40: _ROUTE_PIPE(
    grid, net, extra_cost, margin)

BOUND = (-4, -4, 90, 90)

# Explicit corridors for the two long pipes: BFS otherwise wanders into a shape that
# walls the canvas in half, and every short net then fails.
AP_LEAD = ([(3, y) for y in range(8, 42)] + [(4, 41), (5, 41), (6, 41), (6, 42)])
BR_LEAD = ([(29, y) for y in range(15, 42)] + [(x, 41) for x in range(1, 30)]
           + [(1, y) for y in range(41, 63)] + [(x, 62) for x in range(1, 48)] + [(47, 63)])


def outside(allowed, box=(-3, -3, 80, 72)):
    a = set(allowed)
    return [(x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3])
            if (x, y) not in a]


def build(ap_rect=(6, 42, 40, 8), br_rect=(47, 63, 44, 7, False), verbose=False):
    rt = RT.Router()
    g = RGrid(rt)
    rt.add_input_room(4, 0)
    spl = R.spl(g, 4, 5)
    brel = R.brel(g, 26, 5)
    pcnt = R.pcnt(g, 48, 5)
    crel = R.crel(g, 34, 20)
    acc = R.acc(g, 48, 20)
    arel = R.arel(g, 6, 52)
    mul = R.mul(g, 20, 52)
    rt.add_output_room(65, 29)

    A = lambda r, n: (r.pipes[n][0], r.pipes[n][1])
    W = lambda r, n: r.walls[n]

    def rect_cells(rc):
        x0, y0, w, h = rc[:4]
        right = rc[4] if len(rc) > 4 else True
        lo = x0 if right else x0 - w + 1
        return {(x, y) for x in range(lo, lo + w) for y in range(y0, y0 + h)}

    # --- the two long pipes carry the A queue (>= N*M) and the B ring (>= M*K), so
    # they are drawn by hand as serpentines; the router only sees them as obstacles.
    ap_cells, br_cells = rect_cells(ap_rect), rect_cells(br_rect)
    resv = set(br_cells)
    # every attachment needs TWO free cells straight out of the wall: route_pipe
    # forces a 2-cell stub, so one blocked cell in front makes the net unroutable.
    for room in (spl, pcnt, brel, arel, mul, acc, crel):
        for n in room.pipes:
            ax, ay = A(room, n)
            wx, wy = W(room, n)
            dx, dy = ax - wx, ay - wy
            resv.add((ax, ay))
            resv.add((ax + dx, ay + dy))
    for n, rm in (('AP', spl), ('AP', arel)):
        ax, ay = A(rm, n)
        wx, wy = W(rm, n)
        resv.discard((ax, ay))
        resv.discard((ax + (ax - wx), ay + (ay - wy)))
    br_out = []
    pp_corr = []
    resv |= set()
    for c in resv:
        g.put(c[0], c[1], '\x02', force=True)
    n_ap = route_long(g, A(spl, 'AP'), A(arel, 'AP'), ap_rect, BOUND,
                      end_direction='N', lead_avoid=outside(AP_LEAD))
    for rm, n in ((brel, 'BR'), (mul, 'BR')):
        ax, ay = A(rm, n)
        wx, wy = W(rm, n)
        for c in ((ax, ay), (ax + (ax - wx), ay + (ay - wy))):
            if g.get(*c) == '\x02':
                del g.c[c]
                rt.grid.typ.pop(c, None)
    for c in br_cells | set(br_out):
        if g.get(*c) == '\x02':
            del g.c[c]
            rt.grid.typ.pop(c, None)
    n_br = route_long(g, A(brel, 'BR'), A(mul, 'BR'), br_rect, BOUND,
                      end_direction='N', lead_avoid=outside(BR_LEAD))
    for c in list(resv) + pp_corr:
        if g.get(*c) == '\x02':
            del g.c[c]
            rt.grid.typ.pop(c, None)
    for (x, y), ch in list(g.c.items()):
        if ch in '-|<>^v' and rt.grid.t(x, y) == RT.PLACED:
            rt.grid.set(x, y, RT.PIPE)

    nets = [
        ('IN', (5, 2), W(spl, 'IN')),
        ('CP', W(spl, 'CP'), W(pcnt, 'CP')),
        ('SD', W(spl, 'SD'), W(brel, 'SD')),
        ('CTL', W(pcnt, 'CTL'), W(acc, 'CTL')),
        ('AR', W(arel, 'AR'), W(mul, 'AR')),
        ('BF', W(mul, 'BF'), W(brel, 'BF')),
        ('PP', W(mul, 'PP'), W(acc, 'PP')),
        ('CF', W(acc, 'CF'), W(crel, 'CF')),
        ('CR', W(crel, 'CR'), W(acc, 'CR')),
        ('OUT', W(acc, 'OUT'), (66, 29)),
    ]
    for name, s, d in nets:
        rt.add_pipe_net(s, d, name=name)
    res = rt.solve(budget=60)
    if res is not True:
        raise ValueError(f"router failed: {res.which}: {res.why}")
    return g, n_ap, n_br


if __name__ == '__main__':
    g, n_ap, n_br = build()
    txt = g.render()
    w, h, box = g.footprint()
    print(f"footprint {w}x{h} box={box}  AP={n_ap} cells  BR={n_br} cells",
          file=sys.stderr)
    out = sys.argv[1] if len(sys.argv) > 1 else None
    if out:
        open(out, 'w').write(txt + "\n")
    else:
        print(txt)
