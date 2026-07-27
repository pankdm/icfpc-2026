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
# Every pipe gets an EXPLICIT corridor.  Shortest-path BFS picks lanes that seal a
# room's attachment into a pocket; stating the lane per net is what makes the whole
# grid routable at once.
def col(x, y0, y1):
    return [(x, y) for y in range(min(y0, y1), max(y0, y1) + 1)]


def row(y, x0, x1):
    return [(x, y) for x in range(min(x0, x1), max(x0, x1) + 1)]


AP_LEAD = row(5, 10, 11) + col(10, 2, 5) + [(9, 2)]
AP_EXIT = [(9, 33)] + col(10, 33, 35) + row(35, 10, 17)
BR_LEAD = row(18, 62, 63) + col(63, 2, 18) + [(64, 2)]
BR_EXIT = [(64, 33)] + col(64, 33, 57) + row(57, 28, 64) + col(28, 41, 57) + \
          row(41, 27, 28) + [(27, 40)]

CORR = {
    'IN':  col(13, 0, 1),
    'SD':  col(28, 8, 15) + row(15, 28, 47) + col(47, 15, 18),
    'CP':  col(20, 12, 14) + row(14, 20, 33) + col(33, 12, 14) + row(12, 31, 33),
    'AR':  col(22, 35, 40) + row(35, 22, 27),
    'BF':  col(23, 34, 37) + row(34, 23, 58) + col(58, 24, 34),
    'PP':  row(37, 32, 33) + col(33, 35, 37) + row(35, 33, 60) + col(60, 35, 41) +
           row(41, 52, 60),
    'CF':  row(38, 34, 35) + col(34, 38, 41) + row(41, 33, 34) + col(33, 41, 43) +
           row(43, 32, 33),
    'CR':  [(34, 43), (34, 42), (35, 42), (35, 41)],
    'OUT': row(38, 52, 53),
    'CTL': col(36, 12, 13) + row(13, 36, 62) + col(62, 13, 55) + row(55, 39, 62) +
           col(39, 52, 55),
}


def outside(allowed, box=(-3, -3, 80, 72)):
    a = set(allowed)
    return [(x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3])
            if (x, y) not in a]


def outside(allowed, box=(-4, -5, 78, 60)):
    a = set(allowed)
    return [(x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3])
            if (x, y) not in a]


def build(ap_rect=(9, 2, 10, 32, False), br_rect=(64, 2, 10, 32), verbose=False):
    rt = RT.Router()
    g = RGrid(rt)
    rt.add_input_room(12, -3)
    spl = R.spl(g, 12, 2)
    brel = R.brel(g, 48, 14)
    pcnt = R.pcnt(g, 30, 2)
    arel = R.arel(g, 12, 36)
    mul = R.mul(g, 24, 36)
    crel = R.crel(g, 30, 44)
    acc = R.acc(g, 36, 36)
    rt.add_output_room(54, 37)

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
        ('OUT', A(acc, 'OUT'), (53, 38), 'E'),
        ('CP', A(spl, 'CP'), A(pcnt, 'CP'), 'E'),
        ('CTL', A(pcnt, 'CTL'), A(acc, 'CTL'), 'N'),
    ]
    for name, sp, dp, ed in seq:
        unres(sp, dp, *[c for c in resv
                        if abs(c[0] - sp[0]) + abs(c[1] - sp[1]) <= 1
                        or abs(c[0] - dp[0]) + abs(c[1] - dp[1]) <= 1])
        allow = CORR.get(name)
        stamped = []
        if allow:
            keep = set(allow) | {sp, dp}
            for x in range(-4, 80):
                for y in range(-5, 62):
                    if (x, y) not in keep and g.get(x, y) == ' ':
                        g.put(x, y, '\x03', force=True)
                        stamped.append((x, y))
        try:
            route(g, sp, dp, BOUND, end_direction=ed)
        except Exception as e:
            for c in stamped:
                del g.c[c]
            globals()['_last_grid'] = g
            raise ValueError(f"pipe {name} {sp}->{dp}: {e}")
        for c in stamped:
            if g.get(*c) == '\x03':
                del g.c[c]
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
