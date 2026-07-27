#!/usr/bin/env python3
"""Does the register wall permit pack/unpack with only A and B usable for data?

BP is NOT a data register: no op moves BP into A or B (`m`, `]`, `d`, `a`, `x`, `q`
only read/modify it), so a relay has exactly TWO readable registers.

Claims to test on the oracle-parity Rust engine:
  SPLIT  divisor parked in B, `/` writes quotient->A AND remainder->B in one op,
         so ONE word yields TWO live values with no third register.
  UNBIAS `-` preserves B, so a constant parked in B survives an unbounded loop.
  PACK   acc*base+v needs acc, v and base live at once -> needs the B reload trick.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
from mm2lib import Grid, pipe  # noqa: E402

LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')


def run(g, inp, exp, name, cap=20000):
    path = '/tmp/mm2pack.man'
    open(path, 'w').write(g.render() + '\n')
    o = subprocess.run([LM, '--grade', path, f'--input={inp}', f'--expected={exp}',
                        f'--cap={cap}'], capture_output=True, text=True)
    out = (o.stdout.strip() or o.stderr.strip()[:200])
    ok = '"pass"' in out
    print(f"{name:10s} {'PASS' if ok else 'FAIL'}  {out[:150]}")
    if not ok:
        o2 = subprocess.run([LM, '--grade', path, f'--input={inp}', '--expected=',
                             f'--cap={cap}'], capture_output=True, text=True)
        print('           got:', o2.stdout.strip()[:200])
    return ok


def io(g, y_out=24):
    g.room(0, 0, 3, 3)
    g.put(1, 1, 'I')
    g.room(0, y_out, 3, 3)
    g.put(1, y_out + 1, 'O')


def split_room(g, ox, oy, const):
    """word -> quotient, remainder.  Divisor reloaded per word because `/` eats B."""
    lit = '`' + str(const) + '`'
    body = '@>' + lit + 'Mr/sWsv'
    w = len(body) + 2
    r = g.room(ox, oy, w, 4)
    g.text(ox + 1, oy + 1, body)
    g.text(ox + 2, oy + 2, '^' + '.' * (len(body) - 3) + '<')
    r.attach('IN', 'T', ox + 5, 'in')
    r.attach('OUT', 'B', ox + w - 3, 'out')
    return r


def test_split():
    g = Grid()
    io(g)
    r = split_room(g, 0, 6, 200)
    a_in, a_out = r.pipes['IN'], r.pipes['OUT']
    pipe(g, [(1, 3), (1, 4), (a_in[0], 4), (a_in[0], a_in[1])], 'S')
    pipe(g, [(a_out[0], a_out[1]), (a_out[0], 23), (1, 23)], 'S')
    # 3*200+7 = 607 ; 100*200+199 = 20199
    return run(g, '607 20199', '3 7 100 199', 'SPLIT')


def test_unbias():
    """B parked with 100 for the whole run: `-` and `r` and `s` must all preserve B."""
    g = Grid()
    io(g)
    r = g.room(0, 6, 12, 4)
    g.text(1, 7, "@>`100`Mv")
    g.text(2, 8, "^...s-r<")
    r.attach('IN', 'T', 4, 'in')
    r.attach('OUT', 'B', 6, 'out')
    a_in, a_out = r.pipes['IN'], r.pipes['OUT']
    pipe(g, [(1, 3), (1, 4), (a_in[0], 4), (a_in[0], a_in[1])], 'S')
    pipe(g, [(a_out[0], a_out[1]), (a_out[0], 23), (1, 23)], 'S')
    return run(g, '101 100 199 1 150', '1 0 99 -99 50', 'UNBIAS')


def test_pack():
    """acc = acc*200 + v, four times, then + the bias constant.

    Needs acc, v and 200 live at once -- so B is reloaded every step:
        M ; `200` ; W ; * ; W ; r ; +
    """
    g = Grid()
    io(g)
    step = "M`200`W*Wr+"
    body = '>' + step * 2
    g.room(0, 6, len(body) + 3, 6)
    g.text(1, 7, '@0v')                       # acc = 0
    g.text(1, 8, '^' + '.' * (len(body) - 1) + 'v')
    g.text(1, 9, '>' + step * 2)
    g.text(1, 10, 'v' + '.' * (len(step) * 2 - 1) + '<')
    # after two steps: acc = v0*200+v1 ; send it
    g.put(1, 11, 's') if False else None
    return g


def main():
    ok = [test_split(), test_unbias()]
    print('register wall permits SPLIT+UNBIAS:', all(ok))


if __name__ == '__main__':
    main()
