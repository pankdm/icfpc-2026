#!/usr/bin/env python3
"""matmul rank payoff: how many ranks does an X-fold score improvement buy?"""
import json

d = json.load(open('scratchpad/mm_standings.json'))
rows = d['rows']
full = [r for r in rows if r['casesPassed'] == r['casesTotal'] and r['score'] is not None]
full.sort(key=lambda r: r['score'])
elig = [r for r in rows if r['casesPassed'] > 0]
field = len(elig)
OURS = 230073151
print('full-pass teams:', len(full), 'eligible:', field)
print('leader:', full[0]['teamName'], full[0]['score'])


def rank_of(score):
    # teams ranked below or tied among OTHER eligible teams
    below = 0
    for r in elig:
        if r is None:
            continue
        if r['casesPassed'] < 20 or r['score'] is None:
            below += 1
        elif r['score'] >= score:
            below += 1
    return below


base_below = rank_of(OURS) - 1  # exclude ourselves
base_pts = base_below / (field - 1)
print(f'ours {OURS} -> rankpts {base_pts:.4f}')
for f in [1.5, 2, 3, 5, 8, 10, 20, 27.7]:
    s = OURS / f
    b = rank_of(s) - 1
    print(f'  {f:5.1f}x -> score {s:12.0f}  rankpts {b/(field-1):.4f}  gain {(b - base_below)/(field-1):+.4f}')
