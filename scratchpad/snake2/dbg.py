"""Run one named stress case and show the first differing frame."""
import json, subprocess, sys
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/scratchpad")
sys.path.insert(0, REPO + "/solutions/snake")
LM = REPO + "/interp/target/release/lm"
OUT = "/Users/visenbaev/icfpc26/scratchpad/snake2"

man = sys.argv[1]
name = sys.argv[2]
st = json.load(open(OUT + "/stress.json"))
c = [x for x in st if x["name"] == name][0]
p = subprocess.run([LM, "--grade", man, "--input=" + c["input"],
                    "--expected=" + c["expected"], "--cap=200000",
                    "--frames=" + c["frames"]], capture_output=True, text=True)
print(p.stdout.strip()[:400])
print("rounds:", c["input"])
frames = json.loads(c["frames"])
n = 0
for i, f in enumerate(frames):
    if f:
        n += 1
        if n <= 4 or i >= len(frames) - 2:
            print("-- round %d (frame %d) --" % (i, n))
            for row in f:
                print("   ", row)
