"""Per-room execute/stall attribution for one public matmul case.

The Rust profiler prints cell-level counts on stderr; this maps them onto the mm2
room rectangles so the answer is "ACC stalls 4k ticks", not a cell list.
Usage: prof2.py <case-index> [file.man]
"""
import ast
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LM = os.path.join(ROOT, 'interp', 'target', 'release', 'lm')

# builder-coordinate room rects, and the normalisation the .man render applies
DX, DY = 13, 4
ROOMS = {
    'SPL': (12, 2, 16, 10), 'BREL': (-11, 32, 14, 10), 'PCNT': (32, 2, 13, 10),
    'AREL': (12, 22, 10, 9), 'MUL': (12, 34, 8, 4), 'CREL': (24, 52, 6, 4),
    'ACC': (24, 34, 16, 16), 'IN': (12, -3, 3, 3), 'OUT': (42, 35, 3, 3),
}


def which(x, y):
    for n, (bx, by, w, h) in ROOMS.items():
        if bx + DX <= x <= bx + DX + w - 1 and by + DY <= y <= by + DY + h - 1:
            return n
    return 'pipe'


def main():
    idx = int(sys.argv[1])
    path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, 'solutions', 'matmul', 'matmul-mm2i.man')
    d = json.load(open(os.path.join(ROOT, 'tests', 'matmul.json')))
    case = (d.get('publicTestData') or d.get('testData'))[idx]
    rnd = case['rounds'][0]
    n, m, k = (int(x) for x in rnd['in'][:3])
    macs = n * m * k
    p = subprocess.run([LM, '--profile', path, f"--input={' '.join(rnd['in'])}",
                        f"--expected={' '.join(rnd['out'])}", '--cap=3000000'],
                       capture_output=True, text=True)
    err = p.stderr
    st = json.loads(p.stdout.strip().splitlines()[-1])['settleTick']
    print(f"case {idx} {case['name']}  N={n} M={m} K={k} MACs={macs} "
          f"settle {st}  {st/macs:.2f} t/MAC")

    def grab(key):
        mm = re.search(rf"PROFILE {key}=(\[.*?\])\n", err, re.S)
        return ast.literal_eval(mm.group(1)) if mm else []

    for label in ('cells', 'stalls'):
        per = {}
        for (x, y), c in grab(label):
            per[which(x, y)] = per.get(which(x, y), 0) + c
        tot = sum(per.values())
        line = '  '.join(f"{a}={b}" for b, a in
                         sorted(((v, kk) for kk, v in per.items()), reverse=True))
        print(f"  {label:7s} total {tot:7d} ({tot/max(st,1)*100:5.1f}% of ticks*men)  {line}")

    # hottest individual stall cells, named by room
    for (x, y), c in grab('stalls')[:8]:
        print(f"    stall {c:6d}  ({x},{y}) {which(x, y)}  builder=({x-DX},{y-DY})")


if __name__ == '__main__':
    main()
