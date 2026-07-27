import json, subprocess, sys, os
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
import grade_fast as gf

man = sys.argv[1] if len(sys.argv) > 1 else REPO + "/solutions/snake/fold11.man"
case = sys.argv[2] if len(sys.argv) > 2 else "the long game"
d = json.load(open(REPO + "/tests/snake.json"))
c = [x for x in d["publicTestData"] if x["name"] == case][0]
inp, exp, frames = gf.rounds_of(c)
cmd = [REPO + "/interp/target/release/lm", "--profile", man,
       "--input=" + inp, "--expected=" + exp, "--cap=3000000"]
if frames:
    cmd.append("--frames=" + frames)
out = subprocess.run(cmd, capture_output=True, text=True)
print(out.stdout[:400])
for line in out.stderr.splitlines():
    if line.startswith("PROFILE cells") or line.startswith("PROFILE stalls"):
        print(line[:1500])
    else:
        print(line[:2000])
