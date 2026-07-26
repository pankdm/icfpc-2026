#!/usr/bin/env python3
"""Compare oracle (wasm) vs Rust interp on a literal-semantics probe .man.

usage: python3 run.py <file.man> [steps]
prints: ORACLE {status,output}  RUST {end,output}
"""
import json, subprocess, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def oracle(path):
    p = subprocess.run(['node', 'sim/case.js', path, '[{"in":[],"out":["999999"]}]'],
                       cwd=ROOT, capture_output=True, text=True)
    try:
        j = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {'raw': p.stdout.strip() + p.stderr.strip()[:300]}
    return {'status': j.get('status'), 'reason': j.get('reason'), 'output': j.get('output'),
            'ticks': j.get('ticks'), 'error': j.get('error')}


def rust(path, steps=40):
    p = subprocess.run([os.path.join(ROOT, 'interp/target/release/lm'), path, str(steps)],
                       cwd=ROOT, capture_output=True, text=True)
    lines = [l for l in p.stdout.strip().splitlines() if l.strip()]
    if not lines:
        return {'raw': (p.stdout + p.stderr).strip()[:300]}
    j = json.loads(lines[-1])
    return {'end': j.get('end'), 'output': j.get('output'), 'msg': j.get('message'),
            'step': j.get('step')}


if __name__ == '__main__':
    f = sys.argv[1]
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    o, r = oracle(f), rust(f, steps)
    # 'diverged'/'fail' from the oracle just means our dummy expected output did not match;
    # what we compare is the load verdict, the crash verdict, and the emitted values.
    def kind(status_or_end):
        s = status_or_end or ''
        if s in ('loaderror',):
            return 'loaderror'
        if s in ('crash', 'fatal'):
            return 'fatal'
        return 'ran'
    same = kind(o.get('status')) == kind(r.get('end')) and \
        (o.get('output') or []) == [str(x) for x in (r.get('output') or [])]
    print(f"{os.path.basename(f):28s} ORACLE {json.dumps(o)}")
    print(f"{'':28s} RUST   {json.dumps(r)}   {'MATCH' if same else 'DIVERGE'}")
