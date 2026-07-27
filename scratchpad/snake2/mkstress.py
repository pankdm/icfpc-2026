"""Freeze a stress case set (hand scenarios + fuzz + hunt) as a gate for the
knob search.  Writes scratchpad/snake2/stress.json:
    [{"name":..., "input":..., "expected":..., "frames": <json str>}, ...]
ordered cheap-first so the search can bail on the first failure.
Usage: python3 mkstress.py [n_fuzz] [n_hunt]
"""
import json, os, random, sys
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/scratchpad")
sys.path.insert(0, REPO + "/solutions/snake")
import snake_fuzz as F

NF = int(sys.argv[1]) if len(sys.argv) > 1 else 40
NH = int(sys.argv[2]) if len(sys.argv) > 2 else 40

cases = dict(F.hand_cases())
rng = random.Random(20260727)
for i in range(NF):
    for _ in range(50):
        r = F.random_case(rng, max_rounds=rng.choice([12, 30, 60, 110]),
                          allow_death=(i % 3 != 0))
        if len(r) >= 3:
            break
    cases["fuzz-%03d" % i] = r
for i in range(NH):
    cases["hunt-%03d" % i] = F.hunter_case(
        rng, max_rounds=rng.choice([40, 92, 130]), max_len_cap=rng.choice([8, 20, 45]),
        near=(i % 2 == 0), die_at_end=(i % 3 == 0))
cases = {k: F.trim(v) for k, v in cases.items()}

out = []
# the spec caps a case at 100 rounds; longer games are out of spec and the live
# champion fails them too, so they must not gate the search.
cases = {k: v for k, v in cases.items() if len(v) <= 100}
for name, rounds in cases.items():
    frames = F.expected_frames(rounds)
    out.append({"name": name,
                "input": " / ".join(" ".join(str(t) for t in r) for r in rounds),
                "expected": " / ".join("" for _ in rounds),
                "frames": json.dumps(frames),
                "nrounds": len(rounds)})
out.sort(key=lambda c: c["nrounds"])
json.dump(out, open("/Users/visenbaev/icfpc26/scratchpad/snake2/stress.json", "w"))
print("wrote", len(out), "cases; rounds", out[0]["nrounds"], "..", out[-1]["nrounds"])
