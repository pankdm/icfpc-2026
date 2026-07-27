"""Pick nearest-pipe-legal attachments for a room, honouring fixed choices,
preferred sides, and >=2 spacing between every attachment cell."""
import itertools
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                'solutions', 'matmul'))
from mm2lib import Room                              # noqa: E402


def slots(w, h, sides='TBLR'):
    o = []
    if 'T' in sides:
        o += [('T', i) for i in range(1, w - 1)]
    if 'B' in sides:
        o += [('B', i) for i in range(1, w - 1)]
    if 'L' in sides:
        o += [('L', j) for j in range(1, h - 1)]
    if 'R' in sides:
        o += [('R', j) for j in range(1, h - 1)]
    return o


def cell(w, h, sl):
    s, o = sl
    return {'T': (o, -1), 'B': (o, h), 'L': (-1, o), 'R': (w, o)}[s]


def pick(w, h, pipes, want, fixed=(), pref=None, extra=()):
    """pipes: {name: kind}.  want: {(x,y): name} nearest-pipe requirements.
    fixed: {name: (side, off)}.  pref: {name: 'TBLR' subset}.
    extra: attachment cells of OTHER pipes on this room to keep spaced from."""
    pref = pref or {}
    fixed = dict(fixed)
    free = [n for n in pipes if n not in fixed]
    cand = {n: slots(w, h, pref.get(n, 'TBLR')) for n in free}
    for combo in itertools.product(*[cand[n] for n in free]):
        assign = dict(fixed)
        assign.update(dict(zip(free, combo)))
        cs = [cell(w, h, v) for v in assign.values()] + list(extra)
        bad = False
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                if abs(cs[i][0] - cs[j][0]) + abs(cs[i][1] - cs[j][1]) < 2:
                    bad = True
                    break
            if bad:
                break
        if bad:
            continue
        r = Room(0, 0, w, h)
        for n, sl in assign.items():
            r.attach(n, sl[0], sl[1], pipes[n])
        ok = True
        for c, n in want.items():
            got, strict = r.resolve(c[0], c[1], pipes[n])
            if got != n or not strict:
                ok = False
                break
        if ok:
            return assign
    return None


if __name__ == '__main__':
    SPL_W = {(4, 3): 'AP', (13, 6): 'SD'}
    print('SPL', pick(16, 10, {'AP': 'out', 'SD': 'out', 'CP': 'out'}, SPL_W,
                      fixed={'AP': ('R', 1), 'SD': ('B', 12)},
                      pref={'CP': 'L'}))
    print('SPL alt', pick(16, 10, {'AP': 'out', 'SD': 'out', 'CP': 'out'}, SPL_W,
                          fixed={'AP': ('R', 1), 'SD': ('B', 12)}))
    BREL_W = {(2, 1): 'SD', (3, 1): 'SD', (5, 1): 'SD', (4, 4): 'SD',
              (9, 7): 'BF'}
    print('BREL', pick(14, 10, {'SD': 'in', 'BF': 'in', 'BR': 'out'}, BREL_W,
                       pref={'SD': 'T', 'BF': 'R', 'BR': 'B'}))
    ACC_W = {(7, 5): 'CF', (6, 3): 'CF', (7, 7): 'CF', (9, 2): 'OUT',
             (6, 2): 'CR', (6, 4): 'CR', (8, 4): 'PP', (13, 5): 'PP',
             (3, 12): 'CTL', (3, 13): 'CTL'}
    print('ACC', pick(16, 16, {'CF': 'out', 'OUT': 'out', 'CR': 'in',
                               'PP': 'in', 'CTL': 'in'}, ACC_W,
                      pref={'CF': 'B', 'OUT': 'B', 'CR': 'T', 'PP': 'T',
                            'CTL': 'B'}))
    MUL_W = {(4, 1): 'PP', (3, 2): 'BF', (5, 1): 'AR', (4, 2): 'BR'}
    print('MUL', pick(8, 4, {'PP': 'out', 'BF': 'out', 'AR': 'in', 'BR': 'in'},
                      MUL_W, pref={'PP': 'B', 'BF': 'B', 'AR': 'T', 'BR': 'L'}))
