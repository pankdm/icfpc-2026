import json, sys
d = json.load(open('/Users/visenbaev/icfpc26/tests/brackets.json'))
td = d['publicTestData']
if isinstance(td, str):
    td = json.loads(td)
print(type(td))
json.dump(td, open('/Users/visenbaev/icfpc26/scratchpad/brk2/cases.json','w'), indent=1)
for i, c in enumerate(td if isinstance(td, list) else [td]):
    print(i, json.dumps(c)[:200])
