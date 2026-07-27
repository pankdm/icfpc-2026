#!/usr/bin/env python3
"""Validate the mm2 MACHINE (not its footprint): same nine rooms, but the A queue
and B ring are short serpentines, so it only handles small cases.  If this passes
the 2x2x2 / 2x3x2 / 4x4x4 cases the logic is right and what remains is geometry."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
from mm2lib import RGrid                       # noqa: E402
from mm2route import route_long, route         # noqa: E402
import mm2rooms as R                           # noqa: E402
import router as RT                            # noqa: E402

BOUND = (-4, -4, 120, 120)
_RP = RT.route_pipe
RT.route_pipe = lambda grid, net, extra_cost=None, margin=60: _RP(grid, net, extra_cost, margin)


AP_LEAD = [(3, y) for y in range(8, 18)] + [(4, 17)]
AP_EXIT = [(x, 20) for x in range(9, 24)] + [(9, 21), (23, 19)]
BR_LEAD = ([(33, y) for y in range(15, 18)] + [(x, 17) for x in range(33, 46)]
           + [(45, y) for y in range(18, 34)])
BR_EXIT = ([(45, 36), (45, 37)] + [(x, 37) for x in range(25, 46)]
           + [(25, y) for y in range(26, 38)] + [(x, 26) for x in range(25, 30)])


def outside(allowed, box=(-3, -3, 90, 60)):
    a = set(allowed)
    return [(x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3])
            if (x, y) not in a]


def build(ap_rect=(4, 17, 20, 3), br_rect=(45, 33, 20, 4, False)):
    rt = RT.Router()
    g = RGrid(rt)
    rt.add_input_room(4, 0)
    spl = R.spl(g, 4, 5)
    brel = R.brel(g, 30, 5)
    pcnt = R.pcnt(g, 60, 20)
    arel = R.arel(g, 4, 22)
    mul = R.mul(g, 26, 22)
    crel = R.crel(g, 4, 34)
    acc = R.acc(g, 20, 40)
    rt.add_output_room(40, 42)

    A = lambda r, n: (r.pipes[n][0], r.pipes[n][1])
    W = lambda r, n: r.walls[n]

    resv = set()
    for room in (spl, pcnt, brel, arel, mul, acc, crel):
        for n in room.pipes:
            ax, ay = A(room, n)
            wx, wy = W(room, n)
            resv.add((ax, ay))
            resv.add((ax + (ax - wx), ay + (ay - wy)))
    for rm, n in (('AP', spl), ('AP', arel)):
        pass
    for rm, n in ((spl, 'AP'), (arel, 'AP')):
        ax, ay = A(rm, n)
        wx, wy = W(rm, n)
        resv.discard((ax, ay))
        resv.discard((ax + (ax - wx), ay + (ay - wy)))
    for c in resv:
        g.put(c[0], c[1], '\x02', force=True)
    n_ap = route_long(g, A(spl, 'AP'), A(arel, 'AP'), ap_rect, BOUND, end_direction='N',
                      lead_avoid=outside(AP_LEAD), exit_avoid=outside(AP_EXIT))
    for rm, n in ((brel, 'BR'), (mul, 'BR')):
        ax, ay = A(rm, n)
        wx, wy = W(rm, n)
        for c in ((ax, ay), (ax + (ax - wx), ay + (ay - wy))):
            if g.get(*c) == '\x02':
                del g.c[c]
    n_br = route_long(g, A(brel, 'BR'), A(mul, 'BR'), br_rect, BOUND, end_direction='N',
                      lead_avoid=outside(BR_LEAD), exit_avoid=outside(BR_EXIT))
    for c in list(resv):
        if g.get(*c) == '\x02':
            del g.c[c]
    for (x, y), ch in list(g.c.items()):
        if ch in '-|<>^v' and rt.grid.t(x, y) == RT.PLACED:
            rt.grid.set(x, y, RT.PIPE)

    for c in resv:                    # protect endpoints again for the short nets
        if g.get(*c) == ' ':
            g.put(c[0], c[1], '\x02', force=True)

    def unres(*cells):
        for c in cells:
            if g.get(*c) == '\x02':
                del g.c[c]

    seq = [
        ('IN', (5, 3), A(spl, 'IN'), 'S'),
        ('AR', A(arel, 'AR'), A(mul, 'AR'), 'S'),
        ('SD', A(spl, 'SD'), A(brel, 'SD'), 'E'),
        ('PP', A(mul, 'PP'), A(acc, 'PP'), 'W'),
        ('BF', A(mul, 'BF'), A(brel, 'BF'), 'N'),
        ('CF', A(acc, 'CF'), A(crel, 'CF'), 'S'),
        ('CR', A(crel, 'CR'), A(acc, 'CR'), 'E'),
        ('CP', A(spl, 'CP'), A(pcnt, 'CP'), 'E'),
        ('CTL', A(pcnt, 'CTL'), A(acc, 'CTL'), 'N'),
        ('OUT', A(acc, 'OUT'), (39, 43), 'E'),
    ]
    for name, sp, dp, ed in seq:
        unres(sp, dp, (sp[0] * 2 - 0, sp[1]))
        for c in list(resv):
            if abs(c[0] - sp[0]) + abs(c[1] - sp[1]) <= 1 or \
               abs(c[0] - dp[0]) + abs(c[1] - dp[1]) <= 1:
                unres(c)
        try:
            n = route(g, sp, dp, BOUND, end_direction=ed)
        except Exception as e:
            raise ValueError(f"pipe {name} {sp}->{dp}: {e}")
    return g, n_ap, n_br


if __name__ == '__main__':
    g, n_ap, n_br = build()
    txt = g.render()
    print(f"footprint {g.footprint()}  AP={n_ap} BR={n_br}", file=sys.stderr)
    open('/tmp/mm2small.man', 'w').write(txt + "\n")
    LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')
    for name, inp, exp in [
        ('2x2x2', '2 2 2 1 2 3 4 5 6 7 8', '19 22 43 50'),
        ('2x3x2', '2 3 2 1 2 3 4 5 6 1 2 3 4 5 6', '22 28 49 64'),
        ('3x2x2', '3 2 2 1 0 0 1 1 0 2 1 1 1', '1 0 0 1 2 1'),
    ]:
        o = subprocess.run([LM, '--grade', '/tmp/mm2small.man', f'--input={inp}',
                            f'--expected={exp}', '--cap=200000'], capture_output=True, text=True)
        print(name, o.stdout.strip() or o.stderr.strip()[:200])
