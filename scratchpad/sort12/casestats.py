import json
d = json.load(open('tests/sort-numbers.json'))
pub = d['publicTestData']
mx = 0; tot=0
for c in pub:
    ns = []
    for r in c['rounds']:
        inp = r['in']
        ns.append(int(inp[0]))
    tot += len(c['rounds'])
    mx = max(mx, max(ns))
    print(c['name'], 'rounds', len(c['rounds']), 'n', ns[:12], '...' if len(ns)>12 else '')
print('MAXN', mx, 'total rounds', tot)
