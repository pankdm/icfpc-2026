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

BOUND = (-26, -10, 62, 94)

# Explicit corridors for the two long pipes: BFS otherwise wanders into a shape that
# walls the canvas in half, and every short net then fails.
# Every pipe gets an EXPLICIT corridor.  Shortest-path BFS picks lanes that seal a
# room's attachment into a pocket; stating the lane per net is what makes the whole
# grid routable at once.
def col(x, y0, y1):
    return [(x, y) for y in range(min(y0, y1), max(y0, y1) + 1)]


def row(y, x0, x1):
    return [(x, y) for x in range(min(x0, x1), max(x0, x1) + 1)]


def outside(allowed, box=(-24, -8, 60, 92)):
    a = set(allowed)
    return [(x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3])
            if (x, y) not in a]


# AREL sits NORTH of MUL, so AR arrives on MUL's top wall and BF has the west lane to
# itself -- that is what removes the contention, without widening MUL's ring.
AP_LEAD = row(5, 10, 11) + col(10, 2, 5) + [(9, 2)]
AP_EXIT = [(9, 33)] + col(10, 33, 40) + row(40, 10, 11)
BR_LEAD = col(-13, 56, 60) + row(60, -13, -1) + col(-1, 58, 60) + [(0, 58)]
BR_EXIT = col(0, 73, 74) + row(74, 0, 20) + col(20, 52, 74) + row(52, 15, 20)

CORR = {
    'IN':  col(13, 0, 1),
    'AR':  row(40, 22, 23) + col(23, 40, 46) + row(46, 15, 23) + col(15, 46, 47),
    'BF':  row(49, 10, 11) + col(10, 49, 57) + row(57, -6, 10) + col(-6, 56, 57),
    'SD':  row(8, 28, 29) + col(29, -4, 8) + row(-4, -18, 29) + col(-18, -4, 50) +
           row(50, -18, -17),
    'PP':  row(49, 20, 21) + col(21, 47, 49) + row(47, 21, 48) + col(48, 47, 53) +
           row(53, 40, 48),
    'OUT': row(50, 40, 43),
    'CF':  row(50, 21, 23) + col(21, 50, 70) + row(70, 21, 26),
    'CR':  row(68, 22, 23) + col(22, 53, 68) + row(53, 22, 23),
    'CP':  col(20, 12, 35) + row(35, 20, 50) + col(50, 35, 78) + row(78, 45, 50),
    'CTL': col(38, 65, 73) + row(65, 33, 38) + col(33, 64, 65),
}


def build(ap_rect=(9, 2, 10, 32, False), br_rect=(0, 58, 20, 16), verbose=False):
    rt = RT.Router()
    g = RGrid(rt)
    rt.add_input_room(12, -3)
    spl = R.spl(g, 12, 2)
    brel = R.brel(g, -16, 46)
    pcnt = R.pcnt(g, 32, 74)
    pcnt.attach('CP', 'R', 78, 'in')
    pcnt.attach('CTL', 'T', 38, 'out')
    arel = R.arel(g, 12, 36)
    arel.attach('AP', 'L', 40, 'in')
    arel.attach('AR', 'R', 40, 'out')
    mul = R.mul(g, 12, 48)
    crel = R.crel(g, 24, 66)
    crel.attach('CF', 'B', 26, 'in')
    crel.attach('CR', 'L', 68, 'out')
    acc = R.acc(g, 24, 48)
    acc.attach('CTL', 'B', 33, 'in')
    rt.add_output_room(44, 49)

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
    n_ap = route_long(g, A(spl, 'AP'), A(arel, 'AP'), ap_rect, BOUND, end_direction='E',
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
        ('AR', A(arel, 'AR'), A(mul, 'AR'), 'S'),
        ('SD', A(spl, 'SD'), A(brel, 'SD'), 'E'),
        ('BF', A(mul, 'BF'), A(brel, 'BF'), 'N'),
        ('PP', A(mul, 'PP'), A(acc, 'PP'), 'W'),
        ('CF', A(acc, 'CF'), A(crel, 'CF'), 'N'),
        ('CR', A(crel, 'CR'), A(acc, 'CR'), 'E'),
        ('OUT', A(acc, 'OUT'), (43, 50), 'E'),
        ('CP', A(spl, 'CP'), A(pcnt, 'CP'), 'W'),
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
            for x in range(-24, 60):
                for y in range(-8, 92):
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
