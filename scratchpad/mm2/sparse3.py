#!/usr/bin/env python3
"""mm2 MACHINE validation on a huge sparse canvas with HAND waypoints for every
pipe -- no search, so nothing can tangle.  Footprint is meaningless; this only
answers "does the nine-room engine compute A*B correctly?"."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
from mm2lib import Grid, RGrid, pipe             # noqa: E402
import router as RT                              # noqa: E402
_RP = RT.route_pipe
RT.route_pipe = lambda gr, net, extra_cost=None, margin=18: _RP(gr, net, extra_cost, margin)
from mm2route import snake, pts_expand           # noqa: E402
import mm2rooms as R                             # noqa: E402


def build(apw=20, aph=3, brw=20, brh=3):
    rt = RT.Router()
    g = RGrid(rt)
    rt.add_input_room(6, 0)
    spl = R.spl(g, 6, 6)
    brel = R.brel(g, 40, 6)
    pcnt = R.pcnt(g, 70, 6)
    arel = R.arel(g, 6, 36)
    mul = R.mul(g, 40, 36)
    crel = R.crel(g, 70, 36)
    acc = R.acc(g, 95, 36)
    rt.add_output_room(120, 38)

    A = lambda r, n: (r.pipes[n][0], r.pipes[n][1])
    W = lambda r, n: r.walls[n]

    def lay(pts, end=None):
        pipe(g, pts, end_direction=end)

    # A queue: SPL -> serpentine(10,40) -> AREL
    ap = ([A(spl, 'AP'), (5, 25), (6, 25)] + snake(6, 26, apw, aph)
          + [(25, 33), (11, 33), A(arel, 'AP')])
    lay(pts_expand(ap), 'N')
    # B ring: BREL -> serpentine(70,100) -> MUL
    br = ([A(brel, 'BR'), (36, 16), (36, 58), (40, 58), (40, 59)]
          + snake(40, 60, brw, brh) + [(63, 62), (63, 42), (43, 42), A(mul, 'BR')])
    lay(pts_expand(br), 'N')
    for (x, y), ch in list(g.c.items()):
        if ch in '-|<>^v' and rt.grid.t(x, y) == RT.PLACED:
            rt.grid.set(x, y, RT.PIPE)
    for name, sp, dp in [
        ('IN', (7, 2), W(spl, 'IN')),
        ('SD', W(spl, 'SD'), W(brel, 'SD')),
        ('CP', W(spl, 'CP'), W(pcnt, 'CP')),
        ('AR', W(arel, 'AR'), W(mul, 'AR')),
        ('BF', W(mul, 'BF'), W(brel, 'BF')),
        ('PP', W(mul, 'PP'), W(acc, 'PP')),
        ('CF', W(acc, 'CF'), W(crel, 'CF')),
        ('CR', W(crel, 'CR'), W(acc, 'CR')),
        ('CTL', W(pcnt, 'CTL'), W(acc, 'CTL')),
        ('OUT', W(acc, 'OUT'), (120, 39)),
    ]:
        rt.add_pipe_net(sp, dp, name=name)
    res = rt.solve(budget=25)
    if res is not True:
        raise ValueError(f"router failed: {res.which}: {res.why}")
    return g


if __name__ == '__main__':
    g = build()
    open('/tmp/mm2sparse.man', 'w').write(g.render() + "\n")
    print(f"footprint {g.footprint()}", file=sys.stderr)
    LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')
    for name, inp, exp in [
        ('2x2x2', '2 2 2 1 2 3 4 5 6 7 8', '19 22 43 50'),
        ('2x3x2', '2 3 2 1 2 3 4 5 6 1 2 3 4 5 6', '22 28 49 64'),
        ('3x2x2', '3 2 2 1 0 0 1 1 0 2 1 1 1', '1 0 0 1 2 1'),
        ('neg',   '2 2 2 -1 2 3 -4 5 -6 -7 8', '-9 22 43 -56'),
    ]:
        o = subprocess.run([LM, '--grade', '/tmp/mm2sparse.man', f'--input={inp}',
                            f'--expected={exp}', '--cap=100000'],
                           capture_output=True, text=True)
        print(name, (o.stdout.strip() or o.stderr.strip()[:300]))
