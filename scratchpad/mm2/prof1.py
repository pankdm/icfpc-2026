"""Profile ONE public case with the Rust engine and attribute ticks to rooms.

Usage: prof1.py <case-index> [file.man]
Rooms are identified by the bounding boxes the builder places them at, so the
report says WHICH ROOM stalls, not which cell.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LM = os.path.join(ROOT, 'interp', 'target', 'release', 'lm')

idx = int(sys.argv[1])
path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    ROOT, 'solutions', 'matmul', 'matmul-mm2i.man')

d = json.load(open(os.path.join(ROOT, 'tests', 'matmul.json')))
case = (d.get('publicTestData') or d.get('testData'))[idx]
rnd = case['rounds'][0]
inp = ' '.join(rnd['in'])
exp = ' '.join(rnd['out'])
n, m, k = (int(x) for x in rnd['in'][:3])
macs = n * m * k
print(f"case {idx} {case['name']}  N={n} M={m} K={k}  MACs={macs}")

p = subprocess.run([LM, '--profile', path, f'--input={inp}', f'--expected={exp}',
                    '--cap=3000000'], capture_output=True, text=True)
txt = p.stdout.strip()
try:
    r = json.loads(txt.splitlines()[-1])
except Exception:
    print(txt[-800:])
    sys.exit(1)
st = r.get('settleTick')
print(f"settleTick {st}   {st/macs:.2f} ticks/MAC")
prof = r.get('profile') or r
keys = [kk for kk in prof if kk not in ('status', 'settleTick', 'footprint')]
print('profile keys:', keys[:12])
print(json.dumps({kk: prof[kk] for kk in keys[:6]})[:3000])
