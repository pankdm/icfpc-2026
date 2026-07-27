#!/usr/bin/env python3
"""Delete one row from the tcp left stack and re-grade, to measure which of the
23 rows are load-bearing.

Height 23 = reader(14) + lanes(2) + sweeper(7). 22x22 needs exactly one row
gone. This cuts row R out of the grid entirely (everything below shifts up by
one) and grades the result. A row that survives is a free row; every failure
reports HOW it fails, which is the evidence for why no rewiring exists.

usage: rowcut.py <file.man> [rows...]
"""
import json, subprocess, sys

ROOT = '/Users/visenbaev/icfpc26'


def grade(path):
    out = subprocess.run(['python3', ROOT + '/tools/grade_fast.py', 'tcp', path],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out)
    except Exception:
        return 'unparseable', None
    reasons = {}
    for r in d['results']:
        key = r['status'] + (':' + str(r.get('reason'))[:34] if r.get('reason') else '')
        reasons[key] = reasons.get(key, 0) + 1
    return f"{d['passed']}/{d['total']} " + ' '.join(f'{k}x{v}' for k, v in reasons.items()), d


def main():
    src = sys.argv[1]
    rows = [int(a) for a in sys.argv[2:]] or list(range(1, 23))
    base = open(src).read().rstrip('\n').split('\n')
    for R in rows:
        g = base[:R] + base[R + 1:]
        p = f'/tmp/rowcut{R}.man'
        open(p, 'w').write('\n'.join(g) + '\n')
        verdict, d = grade(p)
        box = d['footprint']['box'] if d else '?'
        print(f'cut row {R:2d}: box {box:4} {verdict}')


main()
