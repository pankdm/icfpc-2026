"""Sweep BOTH ring lengths and report per-case ticks.

The B ring is a closed loop: its LENGTH is the latency a b-value takes to come back
round, so for small M*K it sets ticks/MAC directly (298 cells / M*K values).  Its
capacity floor is M*K <= 256.  DESIGN_mm2 sized it L ~ 1.15*V = 298 by derivation;
this measures the real cliff and what shortening it buys.
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

OUT = '/tmp/ringsweep'
os.makedirs(OUT, exist_ok=True)

AP = (2, 2, 15, 18, False)
BR = (0, 44, 20, 12)


def one(ap, br, tag):
    try:
        g, n_ap, n_br = B.build(ap_rect=ap, br_rect=br)
    except Exception as e:
        print(f"{tag:>12}  BUILD FAIL {str(e)[:60]}", flush=True)
        return
    path = os.path.join(OUT, f"{tag}.man")
    open(path, 'w').write(g.render() + "\n")
    fw, fh, box = g.footprint()
    p = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'grade_fast.py'),
                        'matmul', path], capture_output=True, text=True, timeout=1800)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
        ticks = ' '.join(str(x['settleTick']) if x['status'] == 'pass' else 'X'
                         for x in r['results'])
        st = (f"{r['passed']}/{r['total']} avg {r['avgTicks']:8.0f} "
              f"score {r['score']/1e6:7.2f}M  [{ticks}]")
    except Exception:
        st = "GRADE ERR " + (p.stdout + p.stderr)[-100:].replace('\n', ' ')
    print(f"{tag:>12} AP={n_ap:3d} BR={n_br:3d} {fw}x{fh} box {box}  {st}", flush=True)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'br'
    if mode == 'br':
        for w, h in [(20, 12), (20, 11), (20, 10), (18, 10), (16, 10), (20, 9),
                     (16, 9), (14, 9), (12, 9)]:
            one(AP, (0, 44, w, h), f"br{w}x{h}")
    elif mode == 'ap':
        for w, h in [(14, 16), (14, 15), (13, 17), (14, 14), (13, 16)]:
            one((2, 2, w, h, False), BR, f"ap{w}x{h}")
    else:
        w, h, bw, bh = (int(x) for x in mode.split(','))
        one((2, 2, w, h, False), (0, 44, bw, bh), f"c{w}x{h}_{bw}x{bh}")
