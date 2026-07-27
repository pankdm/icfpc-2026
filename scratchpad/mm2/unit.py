#!/usr/bin/env python3
"""Unit-test the mm2 rooms one at a time: I -> room -> O, with dummy rooms for the
pipes the room needs but the test does not drive.  Catches logic bugs without
solving the whole routing problem."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
from mm2lib import Grid, pipe                    # noqa: E402
import mm2rooms as R                             # noqa: E402
LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')


def run(g, inp, exp, cap=20000, name=''):
    path = f'/tmp/mm2unit.man'
    open(path, 'w').write(g.render() + '\n')
    o = subprocess.run([LM, '--grade', path, f'--input={inp}', f'--expected={exp}',
                        f'--cap={cap}'], capture_output=True, text=True)
    out = (o.stdout.strip() or o.stderr.strip()[:200])
    print(f"{name:8s} {out}")
    if '"pass"' not in out:
        o2 = subprocess.run([LM, '--grade', path, f'--input={inp}', '--expected=',
                             f'--cap={cap}'], capture_output=True, text=True)
        print('         (no-expect run:', o2.stdout.strip()[:200], ')')


def sink(g, x, y):
    """A 5x4 room whose man just parks: somewhere for an unused out-pipe to end."""
    g.room(x, y, 5, 4)
    g.text(x + 1, y + 1, "@H")
    return (x, y)


def test_pcnt():
    g = Grid()
    g.room(0, 0, 3, 3); g.put(1, 1, 'I')
    p = R.pcnt(g, 0, 6)
    g.room(0, 20, 3, 3); g.put(1, 21, 'O')
    A = lambda n: (p.pipes[n][0], p.pipes[n][1])
    pipe(g, [(1, 3), (1, 4), A('CP')[0:2][0] and (A('CP')[0], A('CP')[1])], 'S') \
        if False else None
    # CP is on PCNT's left wall
    pipe(g, [(1, 3), (1, 4), (-1, 4), (-1, A('CP')[1]), A('CP')], 'E')
    pipe(g, [A('CTL'), (A('CTL')[0], 19), (1, 19), (1, 19)], 'S')
    run(g, '3 4 5', '5 5 5 5 5 -5 5 5 5 5 -5 5', name='PCNT')


def test_arel():
    g = Grid()
    g.room(0, 0, 3, 3); g.put(1, 1, 'I')
    a = R.arel(g, 0, 6)
    g.room(0, 20, 3, 3); g.put(1, 21, 'O')
    A = lambda n: (a.pipes[n][0], a.pipes[n][1])
    pipe(g, [(1, 3), (1, 4), (A('AP')[0], 4), A('AP')], 'S')
    ar = A('AR')
    pipe(g, [ar, (ar[0] + 1, ar[1]), (ar[0] + 1, 19), (1, 19)], 'S')
    run(g, '2 3 4 7 8', '7 7 7 7 8 8 8 8', name='AREL')


def test_spl():
    g = Grid()
    g.room(0, 0, 3, 3); g.put(1, 1, 'I')
    s = R.spl(g, 0, 6)
    g.room(0, 24, 3, 3); g.put(1, 25, 'O')
    A = lambda n: (s.pipes[n][0], s.pipes[n][1])
    pipe(g, [(1, 3), (1, 4), (A('IN')[0], 4), A('IN')], 'S')
    pipe(g, [A('AP'), (-4, A('AP')[1]), (-4, 23), (1, 23)], 'S')
    sx, sy = sink(g, 22, 20)
    pipe(g, [A('SD'), (A('SD')[0] + 2, A('SD')[1]), (A('SD')[0] + 2, 18),
             (24, 18), (24, 19)], 'S')
    cx, cy = sink(g, 6, 20)
    pipe(g, [A('CP'), (A('CP')[0], 19), (8, 19)], 'S')
    run(g, '2 2 2 1 2 3 4 5 6 7 8', '2 2 2 1 2 3 4', name='SPL')


def test_brel():
    g = Grid()
    g.room(0, 0, 3, 3); g.put(1, 1, 'I')
    b = R.brel(g, 0, 6)
    g.room(0, 24, 3, 3); g.put(1, 25, 'O')
    A = lambda n: (b.pipes[n][0], b.pipes[n][1])
    sd = A('SD')
    pipe(g, [(1, 3), (1, 4), (-4, 4), (-4, sd[1]), sd], 'E')       # I -> SD (left wall)
    bf = A('BF')                                                   # BF: bottom wall
    sink(g, bf[0] - 2, bf[1] + 3)
    pipe(g, [(bf[0], bf[1] + 2), (bf[0], bf[1])], 'N')
    br = A('BR')                                                   # BR: bottom wall
    pipe(g, [br, (br[0], br[1] + 1), (br[0], 23), (1, 23)], 'S')
    run(g, '2 2 3 11 12 13 14 15 16 99', '11 12 13 14 15 16', name='BREL')


def test_crel():
    g = Grid()
    g.room(0, 0, 3, 3); g.put(1, 1, 'I')
    c = R.crel(g, 0, 6)
    g.room(0, 16, 3, 3); g.put(1, 17, 'O')
    A = lambda n: (c.pipes[n][0], c.pipes[n][1])
    pipe(g, [(1, 3), (1, 4), (A('CF')[0], 4), A('CF')], 'S')
    cr = A('CR')
    pipe(g, [cr, (cr[0], cr[1] + 1), (1, cr[1] + 1), (1, 15)], 'S')
    run(g, '5 6 7', '5 6 7', name='CREL')


def test_acc():
    """I -> PCNT -> (CTL) ACC, with a literal generator feeding ACC's product pipe a
    constant 5.  With N,M,K = 2,2,2 the C ring holds two accumulators, each gets two
    products, so every block emits 10 10.  Exercises seed / MAC ring / the X branch on
    PCNT's -K / the output ring / the re-arm."""
    g = Grid()
    g.room(0, 0, 3, 3); g.put(1, 1, 'I')
    pc = R.pcnt(g, 0, 6)
    acc = R.acc(g, 20, 20)
    crel = R.crel(g, 10, 22)
    g.room(40, 30, 6, 4)                       # GEN: emits 5 forever
    g.text(41, 31, "@>5v")
    g.text(41, 32, " ^s<")
    g.room(38, 21, 3, 3); g.put(39, 22, 'O')
    P = lambda n: (pc.pipes[n][0], pc.pipes[n][1])
    Ac = lambda n: (acc.pipes[n][0], acc.pipes[n][1])
    C = lambda n: (crel.pipes[n][0], crel.pipes[n][1])
    pipe(g, [(1, 3), (1, 4), (-2, 4), (-2, P('CP')[1]), P('CP')], 'E')
    pipe(g, [P('CTL'), (P('CTL')[0], 38), (Ac('CTL')[0], 38), Ac('CTL')], 'N')
    pipe(g, [(39, 31), (38, 31), (38, Ac('PP')[1]), Ac('PP')], 'W')
    pipe(g, [Ac('CF'), (18, Ac('CF')[1]), (18, C('CF')[1]), C('CF')], 'S')
    pipe(g, [C('CR'), (C('CR')[0], 28), (19, 28), Ac('CR')], 'E')
    pipe(g, [Ac('OUT'), (37, Ac('OUT')[1])], 'E')
    run(g, '2 2 2', '10 10 10 10', cap=20000, name='ACC')


def gen(g, x, y, digit):
    """A room that emits `digit` forever: no input room needed."""
    g.room(x, y, 6, 4)
    g.text(x + 1, y + 1, "@>" + digit + "v")
    g.text(x + 2, y + 2, "^s<")
    return (x + 6, y + 1)          # attachment of its single out-pipe (right wall)


def test_mul():
    """Two generators feed MUL's a and b pipes; its products go to O.  MUL's ring is
    entered at `*` so lap 1 emits ONE garbage 0 -- that is by design and ACC's INIT
    discards it."""
    g = Grid()
    g.room(20, -4, 6, 4)                       # GEN a: emits 3 forever, out = bottom
    g.text(21, -3, "@>3v")
    g.text(22, -2, "^s<")
    b_out = gen(g, 0, 10, '7')
    mul = R.mul(g, 20, 5)
    g.room(41, 11, 3, 3); g.put(42, 12, 'O')
    sink(g, 10, 5)
    M = lambda n: (mul.pipes[n][0], mul.pipes[n][1])
    pipe(g, [(23, 0), M('AR')], 'S')
    pipe(g, [b_out, (M('BR')[0], b_out[1]), M('BR')], 'N')
    pipe(g, [M('PP'), (29, M('PP')[1]), (29, 12), (40, 12)], 'E')
    pipe(g, [M('BF'), (15, M('BF')[1])], 'W')
    run(g, '', '0 21 21 21', cap=4000, name='MUL')


if __name__ == '__main__':
    which = sys.argv[1:] or ['pcnt', 'arel', 'spl', 'brel', 'crel', 'acc', 'mul']
    for w in which:
        try:
            globals()['test_' + w]()
        except Exception as e:
            print(f"{w:8s} BUILD ERROR {e}")
