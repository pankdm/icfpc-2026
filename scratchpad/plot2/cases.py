import json
d=json.load(open('tests/plotter.json'))
for c in d['publicTestData']:
    rounds=c['rounds'] if isinstance(c,dict) and 'rounds' in c else None
    print(c.get('name'), list(c.keys()))
    if rounds is not None:
        tot=0
        for r in rounds:
            tot+= 0
        print('  nrounds',len(rounds))
        print('  first round keys', list(rounds[0].keys()) if isinstance(rounds[0],dict) else type(rounds[0]))
