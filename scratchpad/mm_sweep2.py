"""Second-stage sweep of build_dense.py: DX/DY plus the three corridor knobs that
each own a row or column of the bounding box.

  CRD  rows CREL rises toward ACC's underside (its CF attach row is the bottom edge)
  BRT  rows below the B snake before its exit turns east
  APW/APH, BRW/BRH  snake shapes (capacity floors AP >= 254, BR >= 240 measured)

Builds are cheap, grading is not: build everything, keep the ones that are both
smaller than the incumbent and above the capacity floors, then grade those.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
BUILD = os.path.join(REPO, 'solutions/matmul/build_dense.py')
OUT = '/tmp/dense2'
os.makedirs(OUT, exist_ok=True)
AP_MIN, BR_MIN = 256, 242
BOX_MAX = int(os.environ.get('BOX_MAX', '2809'))
KEYS = ('DX', 'DY', 'CRD', 'BRT', 'APW', 'APH', 'BRW', 'BRH')


def one(cfg):
    f = OUT + '/' + '_'.join(str(v) for v in cfg) + '.man'
    env = dict(os.environ, **{k: str(v) for k, v in zip(KEYS, cfg)})
    p = subprocess.run([sys.executable, BUILD, f], env=env,
                       capture_output=True, text=True)
    if p.returncode != 0:
        return None
    parts = p.stderr.strip().splitlines()[-1].split()
    w, h, box, nap, nbr = (int(v) for v in parts[1:6])
    if nap < AP_MIN or nbr < BR_MIN or box > BOX_MAX:
        return None
    return (box, w, h, nap, nbr, f, cfg)


cfgs = [(dx, dy, crd, brt, apw, aph, brw, brh)
        for dx in (8,)
        for dy in (5, 6, 7, 8)
        for crd in (0, 1, 2, 3)
        for brt in (1, 2, 3)
        for apw in (14,)
        for aph in (16, 18)
        for brw in (18, 20)
        for brh in (10, 12)]
with ThreadPoolExecutor(max_workers=8) as ex:
    res = [r for r in ex.map(one, cfgs) if r]
res.sort()
print(f"-- {len(res)}/{len(cfgs)} built within box<={BOX_MAX} and above capacity")


def grade(r):
    p = subprocess.run([sys.executable, os.path.join(REPO, 'tools/grade_fast.py'),
                        'matmul', r[5]], capture_output=True, text=True, cwd=REPO)
    try:
        return r, json.loads(p.stdout)
    except Exception:
        return r, None


with ThreadPoolExecutor(max_workers=4) as ex:
    for r, d in ex.map(grade, res[:24]):
        if not d or d['passed'] != d['total']:
            continue
        print(f"PASS box={r[0]} {r[1]}x{r[2]} AP={r[3]} BR={r[4]} "
              f"score={d['score']:.0f} cfg={dict(zip(KEYS, r[6]))} -> {r[5]}")
