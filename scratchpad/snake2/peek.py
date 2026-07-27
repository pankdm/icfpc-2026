"""Snapshot a run at the tick where it goes wrong: pipes + display."""
import json, subprocess, sys
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/scratchpad")
sys.path.insert(0, REPO + "/solutions/snake")
import snake_fuzz as F
LM = REPO + "/interp/target/release/lm"

man = sys.argv[1]
rounds = json.loads(sys.argv[2])
tick = int(sys.argv[3])
frames = F.expected_frames(rounds)
inp = " / ".join(" ".join(str(t) for t in r) for r in rounds)
p = subprocess.run([LM, "--inspect=%d" % tick, man, "--input=" + inp,
                    "--expected=" + " / ".join("" for _ in rounds),
                    "--cap=200000", "--frames=" + json.dumps(frames)],
                   capture_output=True, text=True)
d = json.loads(p.stdout)
print("step", d["step"], "end", d["end"], "inputRead", d.get("inputRead"))
for i, pi in enumerate(d["pipes"] or []):
    if pi.get("values"):
        print("pipe", i, pi.get("values"))
for i, disp in enumerate(d["displays"] or []):
    for key in ("front", "back", "next"):
        buf = disp.get(key)
        if buf:
            lit = [(j, v) for j, v in enumerate(buf) if v]
            print("display", i, key, "lit:", lit[:12], "cursor", disp.get("cursor"))
print("frameJudge", json.dumps(d.get("frameJudge"))[:300])
