#!/usr/bin/env python3
"""Min-edge-cut 2-partition of the LLM CFG, balanced by controller ROW cost."""
import json, random, collections, sys

d = json.load(open('/tmp/llm_flow.json'))
labels = sorted(d)
idx = {l: i for i, l in enumerate(labels)}
N = len(labels)
W = [d[l]['rows'] for l in labels]
OPS = [d[l]['ops'] for l in labels]
PORTS = [d[l]['ports'] for l in labels]
TOT = sum(W)

E = set()
for l in labels:
    for s in d[l]['succ']:
        if s in idx and s != l:
            E.add((idx[l], idx[s]))
E = sorted(E)
adj = collections.defaultdict(set)
for u, v in E:
    adj[u].add(v)
    adj[v].add(u)

ENTRY = idx['START']


def cost(p):
    return sum(1 for u, v in E if p[u] != p[v])


def targets(p):
    """distinct blocks entered from the other side, per side"""
    t = [set(), set()]
    for u, v in E:
        if p[u] != p[v]:
            t[p[v]].add(v)
    return t


def wsum(p, s):
    return sum(W[i] for i in range(N) if p[i] == s)


def penalty(p, slack):
    a = wsum(p, 0)
    lo, hi = TOT * (0.5 - slack), TOT * (0.5 + slack)
    if a < lo:
        return (lo - a)
    if a > hi:
        return (a - hi)
    return 0.0


def refine(p, slack, iters=40000, rng=None):
    rng = rng or random.Random(0)
    cur = cost(p) + 3.0 * penalty(p, slack)
    for _ in range(iters):
        i = rng.randrange(N)
        p[i] ^= 1
        c = cost(p) + 3.0 * penalty(p, slack)
        if c <= cur:
            cur = c
        else:
            p[i] ^= 1
    return p


def fm(p, slack):
    """greedy best-move passes until no improvement"""
    improved = True
    while improved:
        improved = False
        base = cost(p) + 5.0 * penalty(p, slack)
        best = None
        for i in range(N):
            p[i] ^= 1
            c = cost(p) + 5.0 * penalty(p, slack)
            p[i] ^= 1
            if c < base - 1e-9 and (best is None or c < best[1]):
                best = (i, c)
        if best:
            p[best[0]] ^= 1
            improved = True
    return p


best = None
rng = random.Random(12345)
slack = float(sys.argv[1]) if len(sys.argv) > 1 else 0.06
for trial in range(60):
    if trial == 0:
        # structural seed: SELECT_* on one side
        p = [1 if labels[i].startswith('SELECT') else 0 for i in range(N)]
    elif trial == 1:
        p = [1 if labels[i].startswith(('PIPE', 'SEND', 'RECV')) else 0 for i in range(N)]
    elif trial == 2:
        p = [1 if labels[i].startswith(('COLOR', 'DRAW', 'DIGIT')) else 0 for i in range(N)]
    else:
        p = [rng.randrange(2) for _ in range(N)]
    p = refine(p, slack, 30000, rng)
    p = fm(p, slack)
    if penalty(p, slack) > 0:
        continue
    c = cost(p)
    if best is None or c < best[0]:
        best = (c, list(p))
        print('trial', trial, 'cut', c, 'wA', wsum(p, 0), 'wB', wsum(p, 1), flush=True)

c, p = best
t = targets(p)
print('=' * 60)
print('slack', slack)
print('CUT EDGES', c, 'of', len(E))
print('rows A', wsum(p, 0), 'rows B', wsum(p, 1), 'total', TOT)
print('blocks A', sum(1 for x in p if x == 0), 'B', sum(1 for x in p if x == 1))
print('ops A', sum(OPS[i] for i in range(N) if p[i] == 0),
      'ops B', sum(OPS[i] for i in range(N) if p[i] == 1))
print('entry targets into A', len(t[0]), 'into B', len(t[1]))
print('START in', p[ENTRY])
for s in (0, 1):
    pu = collections.Counter()
    for i in range(N):
        if p[i] == s:
            pu.update(PORTS[i])
    print('side', s, 'ports', dict(pu))
print('cross edges:')
for u, v in E:
    if p[u] != p[v]:
        print(f'  {labels[u]} -> {labels[v]}  ({p[u]}->{p[v]})')
json.dump({labels[i]: p[i] for i in range(N)}, open('/tmp/llm_part.json', 'w'))
