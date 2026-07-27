"""Which walls can each mm2 room's pipes use?  (nearest-pipe legality only)"""
import itertools, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'solutions', 'matmul'))
from mm2lib import Room

def slots(w, h):
    return ([('T', i) for i in range(1, w - 1)] + [('B', i) for i in range(1, w - 1)] +
            [('L', j) for j in range(1, h - 1)] + [('R', j) for j in range(1, h - 1)])

def solve(w, h, want, kind):
    """want: {cell: name}.  Returns {tuple of sides: example assignment}"""
    names = sorted(set(want.values()))
    S = slots(w, h)
    res = {}
    for combo in itertools.product(S, repeat=len(names)):
        if len(set(combo)) != len(names):
            continue
        r = Room(0, 0, w, h)
        for n, sl in zip(names, combo):
            r.attach(n, sl[0], sl[1], kind)
        good = True
        for c, n in want.items():
            got, strict = r.resolve(c[0], c[1], kind)
            if got != n or not strict:
                good = False
                break
        if good:
            key = tuple(s[0] for s in combo)
            res.setdefault(key, (names, combo))
    return res

print("ACC out (CF, OUT):")
for k, v in sorted(solve(16, 16, {(7,5):'CF',(6,3):'CF',(7,7):'CF',(9,2):'OUT'}, 'out').items()):
    print("  ", dict(zip(v[0], v[1])))
print("ACC in (CR, PP, CTL) with PP on T:")
for k, v in sorted(solve(16, 16, {(6,2):'CR',(6,4):'CR',(8,4):'PP',(13,5):'PP',(3,12):'CTL',(3,13):'CTL'}, 'in').items()):
    if k[1] == 'T':
        print("  ", dict(zip(v[0], v[1])))
print("MUL out (BF, PP):")
for k, v in sorted(solve(8, 4, {(4,1):'PP',(3,2):'BF'}, 'out').items()):
    print("  ", dict(zip(v[0], v[1])))
print("MUL in (AR, BR):")
for k, v in sorted(solve(8, 4, {(5,1):'AR',(4,2):'BR'}, 'in').items()):
    print("  ", dict(zip(v[0], v[1])))
print("SPL out (AP, SD, CP):")
for k, v in sorted(solve(16, 10, {(4,3):'AP',(13,6):'SD'}, 'out').items()):
    print("  ", dict(zip(v[0], v[1])))
