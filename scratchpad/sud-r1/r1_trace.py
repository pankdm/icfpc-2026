#!/usr/bin/env python3
"""Print the runner positions at successive ticks for a .man, using lm --inspect."""
import json, subprocess, sys
ROOT = "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg"
LM = ROOT + "/interp/target/release/lm"

man = sys.argv[1]
frames = sys.argv[2] if len(sys.argv) > 2 else "[[0,0,1]]"
lo = int(sys.argv[3]) if len(sys.argv) > 3 else 1
hi = int(sys.argv[4]) if len(sys.argv) > 4 else 16
grid = open(man).read().split("\n")
for t in range(lo, hi + 1):
    r = subprocess.run([LM, "--inspect=%d" % t, man, "--frames=" + frames],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except Exception:
        print(t, "ERR", r.stdout[:120], r.stderr[:120]); break
    runs = d.get("runners") or d.get("men") or []
    def cell(x, y):
        try:
            return grid[y][x]
        except Exception:
            return "?"
    print(t, d.get("end"), [(m.get("x"), m.get("y"), cell(m.get("x"), m.get("y")),
                             m.get("dir"), m.get("a"), m.get("b"))
                            for m in runs])
