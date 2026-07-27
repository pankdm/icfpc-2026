"""Full port solver: for each mm2 room, every nearest-pipe-legal assignment of
ALL its pipes, with attachment cells kept >=2 apart (two adjacent pipe cells
parse as ONE pipe), grouped by the sides used."""
import itertools, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'solutions', 'matmul'))
from mm2lib import Room

def slots(w, h):
    return ([('T', i) for i in range(1, w - 1)] + [('B', i) for i in range(1, w - 1)] +
            [('L', j) for j in range(1, h - 1)] + [('R', j) for j in range(1, h - 1)])

def cell(w, h, sl):
    s, o = sl
    return {'T': (o, -1), 'B': (o, h), 'L': (-1, o), 'R': (w, o)}[s]

def legal(w, h, want, kind, names):
    S = slots(w, h)
    out = []
    for combo in itertools.product(S, repeat=len(names)):
        if len(set(combo)) != len(names):
            continue
        r = Room(0, 0, w, h)
        for n, sl in zip(names, combo):
            r.attach(n, sl[0], sl[1], kind)
        ok = True
        for c, n in want.items():
            got, strict = r.resolve(c[0], c[1], kind)
            if got != n or not strict:
                ok = False
                break
        if ok:
            out.append(dict(zip(names, combo)))
    return out

def spaced(w, h, a, b):
    cs = [cell(w, h, v) for v in list(a.values()) + list(b.values())]
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            if abs(cs[i][0] - cs[j][0]) + abs(cs[i][1] - cs[j][1]) < 2:
                return False
    return True

def report(tag, w, h, wout, nout, win, nin, filt):
    A = legal(w, h, wout, 'out', nout)
    B = legal(w, h, win, 'in', nin)
    hits = []
    for a in A:
        for b in B:
            if not spaced(w, h, a, b):
                continue
            m = {**a, **b}
            if filt(m):
                hits.append(m)
    print(f"{tag}: {len(A)} out x {len(B)} in -> {len(hits)} spaced+filtered")
    for m in hits[:6]:
        print("   ", {k: f"{v[0]}@{v[1]}" for k, v in sorted(m.items())})

report("ACC (PP north, OUT south, CF west)", 16, 16,
       {(7,5):'CF',(6,3):'CF',(7,7):'CF',(9,2):'OUT'}, ['CF','OUT'],
       {(6,2):'CR',(6,4):'CR',(8,4):'PP',(13,5):'PP',(3,12):'CTL',(3,13):'CTL'},
       ['CR','PP','CTL'],
       lambda m: m['PP'][0] == 'T' and m['OUT'][0] == 'B' and m['CF'][0] in 'LB')
report("MUL (PP south, AR/BR west or north)", 8, 4,
       {(4,1):'PP',(3,2):'BF'}, ['PP','BF'],
       {(5,1):'AR',(4,2):'BR'}, ['AR','BR'],
       lambda m: m['PP'][0] == 'B')

report("ACC (PP north; CF/CR/CTL/OUT all south)", 16, 16,
       {(7,5):'CF',(6,3):'CF',(7,7):'CF',(9,2):'OUT'}, ['CF','OUT'],
       {(6,2):'CR',(6,4):'CR',(8,4):'PP',(13,5):'PP',(3,12):'CTL',(3,13):'CTL'},
       ['CR','PP','CTL'],
       lambda m: m['PP'][0]=='T' and m['CF'][0]=='B' and m['CR'][0]=='B'
                 and m['CTL'][0]=='B' and m['OUT'][0] in 'BR')
report("BREL (SD/BF in, BR out)", 14, 10,
       {(3,1):'x'}, [], {}, [], lambda m: True) if False else None
