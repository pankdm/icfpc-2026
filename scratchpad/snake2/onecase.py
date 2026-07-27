"""Run one fuzz-failure scenario against several .man files."""
import json, subprocess, sys, os
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/solutions/snake")
import snake_model as M

LM = REPO + "/interp/target/release/lm"
fails = json.load(open(REPO + "/scratchpad/snake_fuzz_failures.json"))
names = sys.argv[1].split(",") if len(sys.argv) > 1 else None
mans = sys.argv[2].split(",") if len(sys.argv) > 2 else ["solutions/snake/fold11.man"]
sel = [f for f in fails if names is None or f["name"] in names]
for f in sel[:12]:
    rounds = f["rounds"]
    frames = M.expected_frames(rounds) if hasattr(M, "expected_frames") else None
    print(f["name"], rounds if len(str(rounds)) < 200 else "(long)", f["result"]["reason"])
