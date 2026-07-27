"""Exhaustive search over ACC's pipe-attachment walls.

Question: can ACC's OUT port live on a DIFFERENT side from PP?  If not, an
engine whose output leaves the block is non-planar (PP must wrap ACC to reach
the east wall, and its wrap seals whichever pocket OUT sits in) -- which is
exactly why the champion keeps the O room as a pendant inside that pocket.
"""
import itertools, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'solutions', 'matmul'))
from mm2lib import Room

W = H = 16
WANT_OUT = {(7, 5): 'CF', (6, 3): 'CF', (7, 7): 'CF', (9, 2): 'OUT'}
WANT_IN = {(6, 2): 'CR', (6, 4): 'CR', (8, 4): 'PP', (13, 5): 'PP',
           (3, 12): 'CTL', (3, 13): 'CTL'}


def slots():
    out = []
    for i in range(1, W - 1):
        out.append(('T', i))
        out.append(('B', i))
    for j in range(1, H - 1):
        out.append(('L', j))
        out.append(('R', j))
    return out


S = slots()


def side(sl):
    return sl[0]


def ok(assign):
    r = Room(0, 0, W, H)
    for n, sl in assign.items():
        r.attach(n, sl[0], sl[1], 'out' if n in ('CF', 'OUT') else 'in')
    for c, n in WANT_OUT.items():
        got, strict = r.resolve(c[0], c[1], 'out')
        if got != n or not strict:
            return False
    for c, n in WANT_IN.items():
        got, strict = r.resolve(c[0], c[1], 'in')
        if got != n or not strict:
            return False
    return True


found = {}
for cf, o in itertools.product(S, S):
    if cf == o:
        continue
    r = Room(0, 0, W, H)
    r.attach('CF', cf[0], cf[1], 'out')
    r.attach('OUT', o[0], o[1], 'out')
    good = True
    for c, n in WANT_OUT.items():
        got, strict = r.resolve(c[0], c[1], 'out')
        if got != n or not strict:
            good = False
            break
    if good:
        found.setdefault(('OUTSIDE', side(o)), []).append((cf, o))
print("legal (CF,OUT) wall pairs by OUT side:")
for k, v in sorted(found.items()):
    print(f"  OUT on {k[1]}: {len(v)} options, e.g. CF={v[0][0]} OUT={v[0][1]}")
if not found:
    print("  NONE")

fin = {}
for cr, pp, ctl in itertools.product(S, S, S):
    if len({cr, pp, ctl}) != 3:
        continue
    r = Room(0, 0, W, H)
    r.attach('CR', cr[0], cr[1], 'in')
    r.attach('PP', pp[0], pp[1], 'in')
    r.attach('CTL', ctl[0], ctl[1], 'in')
    good = True
    for c, n in WANT_IN.items():
        got, strict = r.resolve(c[0], c[1], 'in')
        if got != n or not strict:
            good = False
            break
    if good:
        fin.setdefault((side(pp), side(ctl)), []).append((cr, pp, ctl))
print("legal (CR,PP,CTL) by (PP side, CTL side):")
for k, v in sorted(fin.items()):
    print(f"  PP={k[0]} CTL={k[1]}: {len(v)}  e.g. {v[0]}")
