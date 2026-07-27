#!/usr/bin/env python3
"""Parallel endgame sweep for unbanked .man files.

scratchpad/unbanked.py grades serially, which cannot get through ~370 candidates
before the deadline.  This runs a process pool and prints only builds that PASS
every public case AND beat the live server score for their slug.
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

AGE = float(os.environ.get('AGE', '5'))
NOW = time.time()
JOBS = int(os.environ.get('JOBS', '10'))

LIVE = {
    'brackets': 95647, 'grade-book': 105758720, 'history-lesson': 6400,
    'matmul': 26899171, 'memory': 5756282, 'pathfinder': 19200000000,
    'plotter': 4516500, 'snake': 39462310, 'sort-numbers': 262915,
    'subset-sum': 2286010829, 'sudoku-validity': 1670038, 'tcp': 314600,
    'reverse-a-list': 13764, 'triangle': 832,
    'little-little-man': None, 'little-little-little-man': None,
}
DIRSLUG = {
    'brackets', 'grade-book', 'history-lesson', 'matmul', 'memory', 'pathfinder',
    'plotter', 'reverse-a-list', 'snake', 'sort-numbers', 'subset-sum',
    'sudoku-validity', 'tcp', 'triangle', 'little-little-man',
    'little-little-little-man',
}
PREFIX = (('ss2', 'subset-sum'), ('subset', 'subset-sum'), ('sud', 'sudoku-validity'),
          ('brk', 'brackets'), ('plot', 'plotter'), ('hist', 'history-lesson'),
          ('snake', 'snake'), ('sort', 'sort-numbers'), ('arm8', 'sort-numbers'),
          ('gb', 'grade-book'), ('mm', 'matmul'), ('pf', 'pathfinder'),
          ('tcp', 'tcp'), ('rev', 'reverse-a-list'), ('tri', 'triangle'),
          ('mem', 'memory'))
SKIP = ('/brk2/', '/brk3/', '/brk4/')


def slug_of(path):
    parts = path.split(os.sep)
    for p in parts:
        if p in DIRSLUG:
            return p
    for key, s in PREFIX:
        if any(p.startswith(key) for p in parts):
            return s
    return None


def grade(arg):
    s, p = arg
    try:
        r = subprocess.run(['python3', 'tools/grade_fast.py', s, p],
                           capture_output=True, text=True, timeout=400)
        d = json.loads(r.stdout.strip().split('\n')[-1])
    except Exception as e:
        return s, p, None, str(e)[:40]
    if d.get('passed') != d.get('total') or not d.get('score'):
        return s, p, None, f"{d.get('passed')}/{d.get('total')}"
    return s, p, d['score'], ''


def main():
    cands = []
    for root in ('solutions', 'scratchpad', 's4'):
        for dirpath, _, files in os.walk(root):
            if any(k in dirpath + '/' for k in SKIP):
                continue
            for f in files:
                if not f.endswith('.man'):
                    continue
                p = os.path.join(dirpath, f)
                try:
                    if (NOW - os.path.getmtime(p)) / 3600.0 > AGE:
                        continue
                except OSError:
                    continue
                s = slug_of(p)
                if s and LIVE.get(s):
                    cands.append((s, p))
    print(f"candidates: {len(cands)}", flush=True)
    best = {}
    done = 0
    with ProcessPoolExecutor(max_workers=JOBS) as ex:
        futs = [ex.submit(grade, c) for c in cands]
        for f in as_completed(futs):
            s, p, sc, why = f.result()
            done += 1
            if done % 25 == 0:
                print(f"  ..{done}/{len(cands)}", flush=True)
            if sc is None:
                continue
            if s not in best or sc < best[s][0]:
                best[s] = (sc, p)
            if sc < LIVE[s]:
                print(f"WIN {s:22s} {sc:>14.0f} < {LIVE[s]:>14.0f}  {p}", flush=True)
    print("\nbest passing local score per slug (live in brackets):")
    for s in sorted(best):
        mark = '  <-- BEATS LIVE' if best[s][0] < LIVE[s] else ''
        print(f"  {s:22s} {best[s][0]:>14.0f}  [{LIVE[s]:>14.0f}] {best[s][1]}{mark}")


if __name__ == '__main__':
    main()
