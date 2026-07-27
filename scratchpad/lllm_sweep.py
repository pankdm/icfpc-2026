"""Build + grade a grid of build3 configurations, ranked by box x ticks.

Every knob here trades box against walking, so neither may be judged alone:
a narrower code room costs rows, a wider one costs a longer walk to the cold
pipe bands.  Only the graded score decides.
"""
import itertools
import json
import os
import subprocess
import sys

ROOT = '/Users/visenbaev/icfpc26'
S4 = os.path.join(ROOT, 's4')
BUILD = 'solutions/little-little-little-man/build3_man.py'


def run(args, out):
    r = subprocess.run([sys.executable, BUILD, out] + args, cwd=S4,
                       capture_output=True, text=True)
    if r.returncode:
        return None, (r.stderr.strip().splitlines() or ['?'])[-1]
    return r.stdout.strip(), None


def grade(path):
    r = subprocess.run([sys.executable, 'tools/grade_fast.py',
                        'little-little-little-man', path],
                       cwd=ROOT, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def main():
    base = sys.argv[1].split() if len(sys.argv) > 1 else []
    grid = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    keys = list(grid)
    rows = []
    for combo in itertools.product(*(grid[k] for k in keys)):
        args = list(base)
        tag = []
        for k, v in zip(keys, combo):
            args += ['--' + k, str(v)]
            tag.append(f"{k}={v}")
        out = '/tmp/sw_' + '_'.join(str(v) for v in combo) + '.man'
        info, err = run(args, out)
        if err:
            print(f"{' '.join(tag):46s} BUILD FAIL {err[:70]}")
            sys.stdout.flush()
            continue
        g = grade(out)
        if not g:
            print(f"{' '.join(tag):46s} GRADE FAIL")
            sys.stdout.flush()
            continue
        if g['passed'] != g['total'] or g.get('avgTicks') is None:
            bad = [r['name'] for r in g['results'] if r['status'] != 'pass']
            print(f"{' '.join(tag):46s} {g['passed']}/{g['total']} FAIL {bad[:3]}")
            sys.stdout.flush()
            continue
        rows.append((g['score'], tag, g, out))
        print(f"{' '.join(tag):46s} {g['passed']}/{g['total']} "
              f"box {g['footprint']['box']:7d} ticks {g['avgTicks']:10.0f} "
              f"score {g['score']:,.0f}")
        sys.stdout.flush()
    rows.sort()
    print("\nBEST:")
    for score, tag, g, out in rows[:5]:
        print(f"  {score:,.0f}  {out}  {' '.join(tag)}")


if __name__ == '__main__':
    main()
