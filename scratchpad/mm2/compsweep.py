"""build -> compact_man -> grade, sweeping band sizes.

compact_man deletes globally redundant rows/cols, which SHORTENS every pipe crossing
them -- so it silently eats ring capacity.  The fix is to oversize the bands in the
builder so the post-compaction pipes still clear the measured floors
(AP >= 254 cells, BR >= 240 cells).  Case 3 (16x16x16) is the only capacity-binding
public case, so it is the fast reject.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import build_mm2p as B  # noqa: E402

LM = os.path.join(ROOT, 'interp', 'target', 'release', 'lm')
OUT = '/tmp/compsweep'
os.makedirs(OUT, exist_ok=True)
SPEC = json.load(open(os.path.join(ROOT, 'tests', 'matmul.json')))
CASES = SPEC['publicTestData']
C3 = CASES[3]['rounds'][0]


def case3(path, cap=200000):
    p = subprocess.run([LM, '--grade', path, f"--input={' '.join(C3['in'])}",
                        f"--expected={' '.join(C3['out'])}", f'--cap={cap}'],
                       capture_output=True, text=True)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {'status': 'err'}


def full(path):
    p = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'grade_fast.py'),
                        'matmul', path], capture_output=True, text=True, timeout=1800)
    return json.loads(p.stdout.strip().splitlines()[-1])


def trial(ap, br):
    tag = f"a{ap[0]}x{ap[1]}_b{br[0]}x{br[1]}"
    raw = os.path.join(OUT, tag + '.man')
    comp = os.path.join(OUT, tag + '_c.man')
    try:
        g, n_ap, n_br = B.build(ap_rect=(2, 2, ap[0], ap[1], False),
                                br_rect=(0, 44, br[0], br[1]))
    except Exception as e:
        print(f"{tag:>18}  BUILD FAIL {str(e)[:50]}", flush=True)
        return None
    open(raw, 'w').write(g.render() + "\n")
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'compact_man.py'),
                        raw, comp], capture_output=True, text=True)
    dims = r.stdout.strip().split('->')[-1].split(';')[0].strip()
    w, h = (int(x) for x in dims.split('x'))
    box = max(w, h) ** 2
    c = case3(comp)
    if c.get('status') != 'pass':
        print(f"{tag:>18} AP={n_ap} BR={n_br} -> {w}x{h} box {box}  "
              f"case3 {c.get('status')}", flush=True)
        return None
    f = full(comp)
    print(f"{tag:>18} AP={n_ap} BR={n_br} -> {w}x{h} box {box}  "
          f"{f['passed']}/{f['total']} avg {f['avgTicks']:.0f} "
          f"score {f['score']/1e6 if f['score'] else -1:.2f}M", flush=True)
    return (f['score'], comp) if f['passed'] == f['total'] else None


if __name__ == '__main__':
    best = None
    combos = []
    for arg in sys.argv[1:]:
        a, b = arg.split('/')
        combos.append((tuple(int(x) for x in a.split('x')),
                       tuple(int(x) for x in b.split('x'))))
    if not combos:
        combos = [((15, 18), (20, 12)), ((16, 20), (20, 14)), ((17, 22), (20, 16)),
                  ((18, 24), (20, 18)), ((16, 22), (22, 14)), ((17, 20), (22, 12))]
    for ap, br in combos:
        r = trial(ap, br)
        if r and (best is None or r[0] < best[0]):
            best = r
    print('BEST', best)
