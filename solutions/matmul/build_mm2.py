import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'tools'))
from mm2lib import RGrid                      # noqa: E402
from mm2route import route_long, route        # noqa: E402
import mm2rooms as R                          # noqa: E402
import router as RT                           # noqa: E402

# the router's default A* box (margin 6 around the two endpoints) is far too tight
# for nets that must detour around a 40-cell serpentine; widen it.
_ROUTE_PIPE = RT.route_pipe
RT.route_pipe = lambda grid, net, extra_cost=None, margin=25: _ROUTE_PIPE(
    grid, net, extra_cost, margin)

BOUND = (-4, -4, 90, 90)

# Explicit corridors for the two long pipes: BFS otherwise wanders into a shape that
# walls the canvas in half, and every short net then fails.
AP_LEAD = [(11, 5), (10, 5)] + [(10, y) for y in range(2, 6)] + [(9, 2)]
AP_EXIT = [(9, 33), (10, 33)] + [(10, y) for y in range(33, 36)] + \
          [(x, 35) for x in range(10, 18)]
BR_LEAD = [(60, 18), (61, 18)] + [(61, y) for y in range(2, 19)] + [(62, 2)]
BR_EXIT = [(62, 33), (61, 33)] + [(61, y) for y in range(33, 44)] + \
          [(x, 43) for x in range(42, 62)] + [(42, y) for y in range(19, 44)] + \
          [(x, 19) for x in range(37, 43)] + [(37, 18)]


def outside(allowed, box=(-3, -3, 80, 72)):
    a = set(allowed)
    return [(x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3])
            if (x, y) not in a]


def outside(allowed, box=(-4, -5, 78, 60)):
    a = set(allowed)
    return [(x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3])
            if (x, y) not in a]


def build(ap_rect=(9, 2, 10, 32, False), br_rect=(62, 2, 10, 32), verbose=False):
    rt = RT.Router()
    g = RGrid(rt)
    rt.add_input_room(12, -3)
    spl = R.spl(g, 12, 2)
    brel = R.brel(g, 46, 14)
    pcnt = R.pcnt(g, 24, 44)
    arel = R.arel(g, 12, 36)
    mul = R.mul(g, 34, 14)
    crel = R.crel(g, 12, 30)
    acc = R.acc(g, 24, 26)
    rt.add_output_room(45, 36)

    A = lambda r, n: (r.pipes[n][0], r.pipes[n][1])
    W = lambda r, n: r.walls[n]

    def rect_cells(rc):
        x0, y0, w, h = rc[:4]
        right = rc[4] if len(rc) > 4 else True
        lo = x0 if right else x0 - w + 1
        return {(x, y) for x in range(lo, lo + w) for y in range(y0, y0 + h)}

    resv = set(rect_cells(br_rect))
    for room in (spl, pcnt, brel, arel, mul, acc, crel):
        for n in room.pipes:
            ax, ay = A(room, n)
            wx, wy = W(room, n)
            resv.add((ax, ay))
            resv.add((ax + (ax - wx), ay + (ay - wy)))
    for rm, n in ((spl, 'AP'), (arel, 'AP')):
        ax, ay = A(rm, n)
        wx, wy = W(rm, n)
        resv.discard((ax, ay))
        resv.discard((ax + (ax - wx), ay + (ay - wy)))
    for c in resv:
        g.put(c[0], c[1], '\x02', force=True)
    n_ap = route_long(g, A(spl, 'AP'), A(arel, 'AP'), ap_rect, BOUND, end_direction='S',
                      lead_avoid=outside(AP_LEAD), exit_avoid=outside(AP_EXIT))
    for rm, n in ((brel, 'BR'), (mul, 'BR')):
        ax, ay = A(rm, n)
        wx, wy = W(rm, n)
        for c in ((ax, ay), (ax + (ax - wx), ay + (ay - wy))):
            if g.get(*c) == '\x02':
                del g.c[c]
    for c in rect_cells(br_rect):
        if g.get(*c) == '\x02':
            del g.c[c]
    n_br = route_long(g, A(brel, 'BR'), A(mul, 'BR'), br_rect, BOUND, end_direction='N',
                      lead_avoid=outside(BR_LEAD), exit_avoid=outside(BR_EXIT))
    for c in list(resv):
        if g.get(*c) == '\x02':
            del g.c[c]
    for (x, y), ch in list(g.c.items()):
        if ch in '-|<>^v' and rt.grid.t(x, y) == RT.PIPE or ch in '-|<>^v':
            rt.grid.set(x, y, RT.PIPE)

    for c in resv:                     # protect endpoints again for the short nets
        if g.get(*c) == ' ':
            g.put(c[0], c[1], '\x02', force=True)

    def unres(*cells):
        for c in cells:
            if g.get(*c) == '\x02':
                del g.c[c]

    seq = [
        ('IN', (13, 0), A(spl, 'IN'), 'S'),
        ('SD', A(spl, 'SD'), A(brel, 'SD'), 'E'),
        ('BF', A(mul, 'BF'), A(brel, 'BF'), 'N'),
        ('AR', A(arel, 'AR'), A(mul, 'AR'), 'S'),
        ('PP', A(mul, 'PP'), A(acc, 'PP'), 'W'),
        ('CF', A(acc, 'CF'), A(crel, 'CF'), 'S'),
        ('CR', A(crel, 'CR'), A(acc, 'CR'), 'E'),
        ('OUT', A(acc, 'OUT'), (44, 37), 'E'),
        ('CP', A(spl, 'CP'), A(pcnt, 'CP'), 'E'),
        ('CTL', A(pcnt, 'CTL'), A(acc, 'CTL'), 'N'),
    ]
    for name, sp, dp, ed in seq:
        unres(sp, dp, *[c for c in resv
                        if abs(c[0] - sp[0]) + abs(c[1] - sp[1]) <= 1
                        or abs(c[0] - dp[0]) + abs(c[1] - dp[1]) <= 1])
        try:
            route(g, sp, dp, BOUND, end_direction=ed)
        except Exception as e:
            globals()['_last_grid'] = g
            raise ValueError(f"pipe {name} {sp}->{dp}: {e}")
    unres(*list(resv))
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
