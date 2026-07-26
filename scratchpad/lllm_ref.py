#!/usr/bin/env python3
"""Reference LLLM simulator + frame renderer (validated against all 10 public cases)."""
import json, sys

COL = {}
for c in "<>^vXH": COL[c] = 3
for c in "0123456789": COL[c] = 8
COL['M'] = 12
COL['+'] = 10
COL['-'] = 10
COL[' '] = 0

DIRS = {'^': (0, -1), '>': (1, 0), 'v': (0, 1), '<': (-1, 0)}
CW = ['^', '>', 'v', '<']


def parse(prog):
    rows = prog.split('\n')
    H = len(rows)
    W = max(len(r) for r in rows)
    rows = [r.ljust(W) for r in rows]
    return W, H, [list(r) for r in rows]


class M:
    def __init__(self, prog):
        self.W, self.H, self.g = parse(prog)
        self.man = None
        for y in range(self.H):
            for x in range(self.W):
                if self.g[y][x] == '@':
                    self.man = (x, y); self.g[y][x] = ' '
        self.d = (1, 0)          # east
        self.a = 0; self.b = 0
        self.halted = False

    def is_wall(self, x, y):
        return x == 0 or y == 0 or x == self.W - 1 or y == self.H - 1

    def step(self):
        if self.halted: return
        x, y = self.man
        c = self.g[y][x]
        if c in DIRS: self.d = DIRS[c]
        elif c.isdigit(): self.a = int(c)
        elif c == 'M': self.b = self.a
        elif c == '+': self.a = self.a + self.b
        elif c == '-': self.a = self.a - self.b
        elif c == 'X':
            if self.a != 0:
                k = CW.index([k for k, v in DIRS.items() if v == self.d][0])
                k = (k + (1 if self.a > 0 else -1)) % 4
                self.d = DIRS[CW[k]]
        elif c == 'H':
            self.halted = True; return
        nx, ny = x + self.d[0], y + self.d[1]
        self.man = (nx, ny)
        if self.is_wall(nx, ny): self.halted = True

    def frame(self):
        f = [[0] * 16 for _ in range(16)]
        for y in range(min(16, self.H)):
            for x in range(min(16, self.W)):
                f[y][x] = 4 if self.is_wall(x, y) else COL.get(self.g[y][x], 0)
        mx, my = self.man
        if 0 <= mx < 16 and 0 <= my < 16: f[my][mx] = 9
        return [''.join('%x' % v for v in row) for row in f]


def make_case(prog, ks):
    W, H, g = parse(prog)
    m = M(prog)
    rounds = [{'in': [str(W), str(H)] + [str(ord(ch)) for row in g for ch in row],
               'frames': [m.frame()], 'out': []}]
    for k in ks:
        for _ in range(k): m.step()
        rounds.append({'in': [str(k)], 'frames': [m.frame()], 'out': []})
    return {'rounds': rounds}


if __name__ == '__main__':
    # self-check against the public cases
    d = json.load(open('/Users/dmitrykorolev/projects/icfpc-2026/tests/little-little-little-man.json'))
    ok = 0
    for i, tc in enumerate(d['publicTestData']):
        rs = tc['rounds']
        v = [int(x) for x in rs[0]['in']]
        W, H = v[0], v[1]
        body = v[2:]
        prog = '\n'.join(''.join(chr(c) for c in body[r * W:(r + 1) * W]) for r in range(H))
        ks = [int(r['in'][0]) for r in rs[1:]]
        mine = make_case(prog, ks)
        good = all(mine['rounds'][j]['frames'][0] == rs[j]['frames'][0] for j in range(len(rs)))
        # also input round-trip
        good = good and mine['rounds'][0]['in'] == rs[0]['in']
        print(i, tc['name'], 'OK' if good else 'MISMATCH')
        ok += good
        if not good:
            for j in range(len(rs)):
                if mine['rounds'][j]['frames'][0] != rs[j]['frames'][0]:
                    print('  round', j); print('  got ', mine['rounds'][j]['frames'][0][:4]);
                    print('  want', rs[j]['frames'][0][:4]); break
    print(ok, '/', len(d['publicTestData']))
