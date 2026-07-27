"""Capacity-aware compaction.

tools/compact_man.py deletes any all-`-` column / all-`|` row that still PARSES.
On mm2 that silently shortens the A queue and the B ring (a `-` column crossing a
band costs one cell per band row), so the 16x16x16 case deadlocks.  Here each
deletion is validated by actually RUNNING the binding cases on the Rust engine.

Usage: safecompact.py <in.man> <out.man> [case indices, default 3 0 6]
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LM = os.path.join(ROOT, 'interp', 'target', 'release', 'lm')
SPEC = json.load(open(os.path.join(ROOT, 'tests', 'matmul.json')))
CASES = SPEC['publicTestData']
TMP = '/tmp/safecompact_try.man'


def rows_of(text):
    lines = text.rstrip('\n').splitlines()
    w = max(map(len, lines))
    return [ln.ljust(w) for ln in lines]


def render(rows):
    out = [r.rstrip() for r in rows]
    while out and not out[-1]:
        out.pop()
    return '\n'.join(out)


def removable_row(rows, i):
    ch = {c for c in rows[i] if c != ' '}
    return not ch or ch == {'|'}


def removable_col(rows, j):
    ch = {r[j] for r in rows if r[j] != ' '}
    return not ch or ch == {'-'}


def ok(rows, idxs, cap):
    open(TMP, 'w').write(render(rows) + '\n')
    for i in idxs:
        rnd = CASES[i]['rounds'][0]
        p = subprocess.run([LM, '--grade', TMP, f"--input={' '.join(rnd['in'])}",
                            f"--expected={' '.join(rnd['out'])}", f'--cap={cap}'],
                           capture_output=True, text=True)
        try:
            if json.loads(p.stdout.strip().splitlines()[-1])['status'] != 'pass':
                return False
        except Exception:
            return False
    return True


def main():
    src, dst = sys.argv[1], sys.argv[2]
    idxs = [int(x) for x in sys.argv[3:]] or [3, 0, 6]
    cap = 150000
    rows = rows_of(open(src).read())
    print(f"start {len(rows[0])}x{len(rows)}", flush=True)
    changed = True
    while changed:
        changed = False
        for i in range(len(rows)):
            if not removable_row(rows, i):
                continue
            cand = rows[:i] + rows[i + 1:]
            if ok(cand, idxs, cap):
                rows = cand
                print(f"  -row {i} -> {len(rows[0])}x{len(rows)}", flush=True)
                changed = True
                break
        if changed:
            continue
        for j in range(len(rows[0])):
            if not removable_col(rows, j):
                continue
            cand = [r[:j] + r[j + 1:] for r in rows]
            if ok(cand, idxs, cap):
                rows = cand
                print(f"  -col {j} -> {len(rows[0])}x{len(rows)}", flush=True)
                changed = True
                break
    w, h = len(rows[0]), len(rows)
    open(dst, 'w').write(render(rows) + '\n')
    print(f"done {w}x{h} box {max(w,h)**2} -> {dst}")


if __name__ == '__main__':
    main()
