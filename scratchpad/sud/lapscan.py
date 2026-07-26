#!/usr/bin/env python3
"""Find the real timer cliff: shrink LAP until the oracle stops passing.
LAP = 2*(43 - timer_left)."""
import subprocess, sys, os
SOL = "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/solutions/sudoku-validity"
for left in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
    subprocess.run([sys.executable, f"{SOL}/build_lanes3.py", str(left), "probe.man"],
                   capture_output=True)
    out = subprocess.run(["node", "tools/grade.js", "sudoku-validity", f"{SOL}/probe.man"],
                         cwd="/Users/visenbaev/icfpc26", capture_output=True, text=True).stdout
    npass = [l for l in out.splitlines() if "public" in l]
    score = [l for l in out.splitlines() if "SCORE" in l]
    print(f"LAP={2*(43-left):3d}", npass[0].split()[-2:] if npass else "?",
          score[0].split()[-1] if score else "-")
os.path.exists(f"{SOL}/probe.man") and os.remove(f"{SOL}/probe.man")
