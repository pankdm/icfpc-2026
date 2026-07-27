#!/usr/bin/env python3
"""Build snake3_build.py with push10's config and grade it against the champion.

  python3 snake3_try.py [tag]
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

CFG = json.load(open(os.path.join(HERE, "push10-cfg.json")))
import snake3_build as B  # noqa: E402

tag = sys.argv[1] if len(sys.argv) > 1 else "reorder"
out = os.path.join(HERE, f"snake3-{tag}.man")
prog, cap, nrows = B.fit(save_to=out, **CFG)
print("built", prog.footprint(), "ring cap", cap, "ctrl rows", nrows)
g = subprocess.run([sys.executable, os.path.join(REPO, "tools", "grade_fast.py"),
                    "snake", out], capture_output=True, text=True)
d = json.loads(g.stdout.strip().splitlines()[-1])
print(f"pass {d['passed']}/{d['total']} box {d['footprint']['box']} "
      f"ticks {d['avgTicks']} score {d['score']:.0f}   (champion 4096 / 6901.0 / 28266496)")
for r in d["results"]:
    print(f"   {r['name']:24s} {r['status']:6s} {r['settleTick']}")
