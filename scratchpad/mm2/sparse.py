#!/usr/bin/env python3
"""Validate the mm2 MACHINE on a deliberately huge, sparse canvas where routing
cannot fail.  Footprint is meaningless here; correctness of the nine-room engine
is the only question this answers."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
from mm2lib import Grid                          # noqa: E402
from mm2route import route_long, route           # noqa: E402
import mm2rooms as R                             # noqa: E402

BOUND = (-5, -5, 260, 200)


def build(apw=20, aph=3, brw=20, brh=3):
    g = Grid()
    g.room(10, 0, 3, 3)
    g.put(11, 1, 'I')
    spl = R.spl(g, 10, 10)
    brel = R.brel(g, 70, 10)
    pcnt = R.pcnt(g, 130, 90)
    arel = R.arel(g, 10, 60)
    mul = R.mul(g, 70, 60)
    crel = R.crel(g, 155, 66)
    acc = R.acc(g, 170, 60)
    g.room(215, 62, 3, 3)
    g.put(216, 63, 'O')

    A = lambda r, n: (r.pipes[n][0], r.pipes[n][1])
    W = lambda r, n: r.walls[n]
    rooms = (spl, pcnt, brel, arel, mul, acc, crel)

    def reserve():
        rs = set()
        for room in rooms:
            for n in room.pipes:
                ax, ay = A(room, n)
                wx, wy = W(room, n)
                rs.add((ax, ay))
                rs.add((ax + (ax - wx), ay + (ay - wy)))
        return rs

    resv = reserve()

    def stamp(cells):
        for c in cells:
            if g.get(*c) == ' ':
                g.put(c[0], c[1], '\x02', force=True)

    def unstamp(cells):
        for c in cells:
            if g.get(*c) == '\x02':
                del g.c[c]

    def ends(room, name):
        ax, ay = A(room, name)
        wx, wy = W(room, name)
        return [(ax, ay), (ax + (ax - wx), ay + (ay - wy))]

    stamp(resv)
    unstamp(ends(spl, 'AP') + ends(arel, 'AP'))
    n_ap = route_long(g, A(spl, 'AP'), A(arel, 'AP'), (10, 40, apw, aph), BOUND,
                      end_direction='N')
    unstamp(ends(brel, 'BR') + ends(mul, 'BR'))
    n_br = route_long(g, A(brel, 'BR'), A(mul, 'BR'), (70, 100, brw, brh), BOUND,
                      end_direction='N')

    seq = [
        ('IN', (11, 3), A(spl, 'IN'), 'S'),
        ('OUT', A(acc, 'OUT'), (214, 63), 'E'),
        ('SD', A(spl, 'SD'), A(brel, 'SD'), 'E'),
        ('CP', A(spl, 'CP'), A(pcnt, 'CP'), 'E'),
        ('AR', A(arel, 'AR'), A(mul, 'AR'), 'S'),
        ('PP', A(mul, 'PP'), A(acc, 'PP'), 'W'),
        ('BF', A(mul, 'BF'), A(brel, 'BF'), 'N'),
        ('CF', A(acc, 'CF'), A(crel, 'CF'), 'S'),
        ('CR', A(crel, 'CR'), A(acc, 'CR'), 'E'),
        ('CTL', A(pcnt, 'CTL'), A(acc, 'CTL'), 'N'),
    ]
    for name, sp, dp, ed in seq:
        unstamp([sp, dp] + [c for c in resv
                            if abs(c[0] - sp[0]) + abs(c[1] - sp[1]) <= 1
                            or abs(c[0] - dp[0]) + abs(c[1] - dp[1]) <= 1])
        try:
            route(g, sp, dp, BOUND, end_direction=ed)
        except Exception as e:
            raise ValueError(f"pipe {name} {sp}->{dp}: {e}")
    unstamp(list(resv))
    return g, n_ap, n_br


if __name__ == '__main__':
    g, n_ap, n_br = build()
    open('/tmp/mm2sparse.man', 'w').write(g.render() + "\n")
    print(f"footprint {g.footprint()}  AP={n_ap} BR={n_br}", file=sys.stderr)
    LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')
    for name, inp, exp in [
        ('2x2x2', '2 2 2 1 2 3 4 5 6 7 8', '19 22 43 50'),
        ('2x3x2', '2 3 2 1 2 3 4 5 6 1 2 3 4 5 6', '22 28 49 64'),
        ('3x2x2', '3 2 2 1 0 0 1 1 0 2 1 1 1', '1 0 0 1 2 1'),
    ]:
        o = subprocess.run([LM, '--grade', '/tmp/mm2sparse.man', f'--input={inp}',
                            f'--expected={exp}', '--cap=100000'],
                           capture_output=True, text=True)
        print(name, (o.stdout.strip() or o.stderr.strip()[:300]))
