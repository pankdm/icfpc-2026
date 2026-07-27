#!/usr/bin/env python3
"""Profile one pathfinder case and rank cells by cost.

Two rankings, because they answer different questions:
  * by TICKS   -- where the clock actually goes
  * by len*count of blank runs -- long corridors walked a few times, which
    tick-ranked profiles hide (gradebook's biggest win was one of these)

usage: pf3_prof.py <file.man> [case_index] [--runs]
"""
import json, subprocess, sys, collections, os, re

ROOT = '/Users/visenbaev/icfpc26'
LM = ROOT + '/interp/target/release/lm'
SPEC = json.load(open(ROOT + '/tests/pathfinder.json'))['publicTestData']


def rounds_of(tc):
    rs = tc['rounds']
    inp = '/'.join(' '.join(str(v) for v in r.get('in', [])) for r in rs)
    exp = '/'.join(' '.join(str(v) for v in r.get('out', [])) for r in rs)
    per = [r.get('frames') or [] for r in rs]
    return inp, exp, (json.dumps(per) if any(per) else '')


def run(man, idx, cap, extra):
    tc = SPEC[idx]
    inp, exp, frames = rounds_of(tc)
    cmd = [LM, man, '--grade', f'--input={inp}', f'--expected={exp}', f'--cap={cap}'] + extra
    if frames:
        cmd.append(f'--frames={frames}')
    return subprocess.run(cmd, capture_output=True, text=True, timeout=1800)


def main():
    man = sys.argv[1]
    idx = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith('-') else 1
    # settle tick first, so --cap does not profile millions of parked ticks
    p = run(man, idx, 5_000_000, [])
    st = json.loads(p.stdout)['settleTick']
    print(f"case {idx} {SPEC[idx]['name']!r} settleTick {st}")
    p = run(man, idx, st, ['--profile'])
    txt = p.stderr
    open('/tmp/pf3prof.txt', 'w').write(txt)
    print('profile bytes', len(txt))
    print(txt[:400])


main()
