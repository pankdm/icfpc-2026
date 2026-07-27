"""Run ad-hoc round lists against a .man and report pass/fail.
Usage: python3 adhoc.py <man> '<rounds json>' [...]
"""
import json, subprocess, sys
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/scratchpad")
sys.path.insert(0, REPO + "/solutions/snake")
import snake_fuzz as F
LM = REPO + "/interp/target/release/lm"

man = sys.argv[1]
for arg in sys.argv[2:]:
    rounds = json.loads(arg)
    v = F.run_case(man, rounds, 100000)
    print("%-8s %-40s %s" % (v.get("status"), arg, str(v.get("reason", ""))[:60]))
