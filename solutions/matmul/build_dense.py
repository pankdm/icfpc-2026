"""build_dense — mm2j's floorplan with the dead space squeezed out.

mm2j is 60x60 with only 40% of the box occupied: a 44x18 void sits between SPL/PCNT
(rows 2..11) and AREL (row 22), and a 9-column gutter sits between the A band's east
edge (col 2) and SPL's west wall (col 12).  Both are pure slack.

Everything here is a RIGID group shift of the champion, so every nearest-pipe binding
is preserved by construction (`_nearest_pipe` compares only the pipe's terminal cell,
so lanes hugging a foreign wall are harmless -- what is NOT harmless is an arrow whose
backward neighbour is a room border, which starts a spurious pipe; the corridors below
keep every turn off a wall).

    DX  columns the centre+east group moves west   (shrinks the A-band gutter)
    DY  rows the southern group moves up           (closes the mid-canvas void)

The A band stays anchored to the west strip and BREL keeps its column, so the west
edge is fixed; the B band travels with MUL because its exit lane runs beside it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'tools'))
from mm2lib import RGrid                      # noqa: E402
from mm2route import route_long, route        # noqa: E402
import mm2rooms as R                          # noqa: E402
import router as RT                           # noqa: E402

_ROUTE_PIPE = RT.route_pipe
RT.route_pipe = lambda grid, net, extra_cost=None, margin=25: _ROUTE_PIPE(
    grid, net, extra_cost, margin)

BOUND = (-26, -10, 62, 94)

DX = int(os.environ.get('DX', '6'))
DY = int(os.environ.get('DY', '8'))
# CRD: extra rows CREL rises toward ACC's underside (its CF attach row is the
# program's bottom edge, so every row here is a row of box).
CRD = int(os.environ.get('CRD', '0'))


def col(x, y0, y1):
    return [(x, y) for y in range(min(y0, y1), max(y0, y1) + 1)]


def row(y, x0, x1):
    return [(x, y) for x in range(min(x0, x1), max(x0, x1) + 1)]


def outside(allowed, box=(-24, -8, 60, 92)):
    a = set(allowed)
    return [(x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3])
            if (x, y) not in a]


def ap_exit(rect):
    x0, y0, w, h = rect[:4]
    lo = x0 - w + 1
    tx = lo if (h - 1) % 2 == 0 else x0
    ty = y0 + h - 1
    return col(tx, ty, 26 - DY) + row(26 - DY, tx, 11 - DX)


def br_lead(rect):
    x0 = rect[0]
    return col(-8, 42 - DY, 46 - DY) + row(46 - DY, -8, x0 - 1) + \
        col(x0 - 1, 44 - DY, 46 - DY) + [(x0, 44 - DY)]


def br_exit(rect):
    x0, y0, w, h = rect[:4]
    tx = (x0 + w - 1) if (h - 1) % 2 == 0 else x0
    ty = y0 + h - 1
    lane = 20 - DX
    # turn immediately below the snake instead of at the old fixed row 56: that row
    # was the whole program's bottom edge and nothing else needs it.
    tr = ty + int(os.environ.get('BRT', '1'))
    return col(tx, ty, tr) + row(tr, min(tx, lane), max(tx, lane)) + \
        col(lane, 38 - DY, tr) + row(38 - DY, 15 - DX, lane)


AP_LEAD = row(5, 10 - DX, 11 - DX) + col(10 - DX, 2, 5) + row(2, 3, 10 - DX)
# BREL's SD attachment is at x = -12, so SD's descent lane must be <= -12 and must
# clear the A band, whose west edge is 2 - APW + 1.
SDX = min(-12, 2 - int(os.environ.get('APW', '14')))

CORR = {
    'IN':  col(13 - DX, 0, 1),
    'AR':  row(26 - DY, 22 - DX, 23 - DX) + col(23 - DX, 26 - DY, 32 - DY) +
           row(32 - DY, 15 - DX, 23 - DX) + col(15 - DX, 32 - DY, 33 - DY),
    'BF':  row(35 - DY, 10 - DX, 11 - DX) + col(10 - DX, 35 - DY, 43 - DY) +
           row(43 - DY, -1, 10 - DX) + col(-1, 42 - DY, 43 - DY),
    # SDX: the column SD descends on.  It only has to clear the A band's west edge
    # (x0 - APW + 1), so it follows the band instead of sitting at a fixed -13.
    'SD':  row(11, 28 - DX, 29 - DX) + col(29 - DX, -4, 11) + row(-4, SDX, 29 - DX) +
           col(SDX, -4, 36 - DY) + row(36 - DY, SDX, -12),
    'PP':  row(35 - DY, 20 - DX, 21 - DX) + col(21 - DX, 33 - DY, 35 - DY) +
           row(33 - DY, 21 - DX, 46 - DX) + col(46 - DX, 33 - DY, 39 - DY) +
           row(39 - DY, 40 - DX, 46 - DX),
    'OUT': row(36 - DY, 40 - DX, 41 - DX),
    'CF':  row(36 - DY, 21 - DX, 23 - DX) + col(21 - DX, 36 - DY, 56 - DY - CRD) +
           row(56 - DY - CRD, 21 - DX, 26 - DX),
    'CR':  row(54 - DY - CRD, 22 - DX, 23 - DX) +
           col(22 - DX, 39 - DY, 54 - DY - CRD) + row(39 - DY, 22 - DX, 23 - DX),
    'CP':  col(20 - DX, 12, 13) + row(13, 20 - DX, 30 - DX) +
           col(30 - DX, 6, 13) + [(31 - DX, 6)],
    'CTL': col(38 - DX, 12, 13) + row(13, 31 - DX, 47 - DX) +
           col(47 - DX, 13, 51 - DY) + row(51 - DY, 33 - DX, 47 - DX) +
           col(33 - DX, 50 - DY, 51 - DY),
}


def build(ap_rect=None, br_rect=None, verbose=False):
    if ap_rect is None:
        ap_rect = (2, 2, int(os.environ.get('APW', '14')),
                   int(os.environ.get('APH', '16')), False)
    if br_rect is None:
        br_rect = (0 - DX, 44 - DY, int(os.environ.get('BRW', '18')),
                   int(os.environ.get('BRH', '10')))
    rt = RT.Router()
    g = RGrid(rt)
    rt.add_input_room(12 - DX, -3)
    spl = R.spl(g, 12 - DX, 2)
    brel = R.brel(g, -11, 32 - DY)
    pcnt = R.pcnt(g, 32 - DX, 2)
    pcnt.attach('CP', 'L', 6, 'in')
    arel = R.arel(g, 12 - DX, 22 - DY)
    arel.attach('AP', 'L', 26 - DY, 'in')
    arel.attach('AR', 'R', 26 - DY, 'out')
    mul = R.mul(g, 12 - DX, 34 - DY)
    crel = R.crel(g, 24 - DX, 52 - DY - CRD)
    crel.attach('CF', 'B', 26 - DX, 'in')
    crel.attach('CR', 'L', 54 - DY - CRD, 'out')
    acc = R.acc(g, 24 - DX, 34 - DY)
    acc.attach('CTL', 'B', 33 - DX, 'in')
    rt.add_output_room(42 - DX, 35 - DY)

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
                      lead_avoid=outside(AP_LEAD), exit_avoid=outside(ap_exit(ap_rect)))
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
                      lead_avoid=outside(br_lead(br_rect)),
                      exit_avoid=outside(br_exit(br_rect)))
    for c in list(resv):
        if g.get(*c) == '\x02':
            del g.c[c]
    for (x, y), ch in list(g.c.items()):
        if ch in '-|<>^v' and rt.grid.t(x, y) == RT.PIPE or ch in '-|<>^v':
            rt.grid.set(x, y, RT.PIPE)

    for c in resv:
        if g.get(*c) == ' ':
            g.put(c[0], c[1], '\x02', force=True)

    def unres(*cells):
        for c in cells:
            if g.get(*c) == '\x02':
                del g.c[c]

    seq = [
        ('IN', (13 - DX, 0), A(spl, 'IN'), 'S'),
        ('AR', A(arel, 'AR'), A(mul, 'AR'), 'S'),
        ('SD', A(spl, 'SD'), A(brel, 'SD'), 'E'),
        ('BF', A(mul, 'BF'), A(brel, 'BF'), 'N'),
        ('PP', A(mul, 'PP'), A(acc, 'PP'), 'W'),
        ('CF', A(acc, 'CF'), A(crel, 'CF'), 'N'),
        ('CR', A(crel, 'CR'), A(acc, 'CR'), 'E'),
        ('OUT', A(acc, 'OUT'), (41 - DX, 36 - DY), 'E'),
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
    print(f"RES {w} {h} {box} {n_ap} {n_br}",
          file=sys.stderr)
    out = sys.argv[1] if len(sys.argv) > 1 else None
    if out:
        open(out, 'w').write(txt + "\n")
    else:
        print(txt)
