"""Decisive: can the three SHORT pipes (input->main, main->relay, main->output)
coexist at all in the box?  Collects many candidate paths per pipe and looks for
three pairwise-disjoint ones.  Ignores every semantic constraint."""
import os, sys
from collections import Counter
sys.path.insert(0, 'scratchpad/sort12')
import search as S, drive
c = Counter(); seen = set()

def collect(p, kind, cap=400):
    out = []
    if kind == 'in':
        pairs = [(a, b) for a in p.srcs('inp') for b in p.dsts('main')]
        hi = 22
    elif kind == 'rel':
        pairs = [(a, b) for a in p.srcs('main') for b in p.dsts('relay')]
        hi = 12
    else:
        pairs = [(a, b) for a in p.srcs('main') for b in p.dsts('outp')]
        hi = 12
    for (s, sd), (e, ed) in pairs:
        if s == e: continue
        for path in S.route(p, s, sd, e, ed, set(), 2, hi, want=6, budget=12000):
            out.append(frozenset(path[0]))
            if len(out) >= cap: return out
    return out

for mgrid, arole, rooms in drive.plans():
    k = tuple(sorted(rooms.items()))
    if k in seen: continue
    seen.add(k)
    p = S.Plan(rooms)
    if len(p.free) < 21: continue
    c['plans'] += 1
    A = collect(p, 'in'); B = collect(p, 'rel'); C = collect(p, 'out')
    c['has_in'] += len(A) > 0; c['has_rel'] += len(B) > 0; c['has_out'] += len(C) > 0
    ok = False
    for a in A:
        for b in B:
            if a & b: continue
            c['in+rel'] += 1
            for d in C:
                if (a | b) & d: continue
                ok = True; break
            if ok: break
        if ok: break
    if ok:
        c['THREE'] += 1
        if c['THREE'] <= 3: print('3-pipe ok', rooms, flush=True)
print('FINAL', dict(c))
