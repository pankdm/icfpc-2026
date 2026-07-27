import sys, os, json, collections
HERE='/Users/dmitrykorolev/projects/icfpc-2026-main/solutions/little-little-man'
sys.path.insert(0,HERE)
from verify_subset import run_flow
import build_banked_dedup as builder
spec=json.load(open('/Users/dmitrykorolev/projects/icfpc-2026-main/tests/little-little-man.json'))
part=json.load(open('/tmp/llm_part_002.json'))
tot=collections.Counter(); trans=collections.Counter(); ticks_tot=0
state={'prev':None}
def mk():
    state['prev']=None
    def observe(label, token):
        if label!=state['prev']:
            if state['prev'] is not None:
                trans[(state['prev'],label)]+=1
            state['prev']=label
        tot[label]+=1
    return observe
for case in spec['publicTestData']:
    _,t=run_flow(case['rounds'], limit=20_000_000, builder=builder, token_hook=mk())
    ticks_tot+=t
print('flow-op total across 14 public cases', ticks_tot)
cross=[(u,v) for (u,v),n in trans.items() if part.get(u,-1)!=part.get(v,-1) and u in part and v in part]
n_cross=sum(trans[e] for e in cross)
print('total block transitions', sum(trans.values()))
print('cross transitions', n_cross, f'({100*n_cross/sum(trans.values()):.2f}%)')
for e in sorted(cross,key=lambda e:-trans[e]):
    print(f'  {e[0]:28s} -> {e[1]:28s} {trans[e]:9d}  ({part.get(e[0])}->{part.get(e[1])})')
print('per-case cross', n_cross/14)
print('total flow ops', sum(tot.values()))
json.dump({f'{u}|{v}':n for (u,v),n in trans.items()}, open('/tmp/llm_trans.json','w'))
