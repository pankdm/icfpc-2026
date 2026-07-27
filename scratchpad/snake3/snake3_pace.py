#!/usr/bin/env python3
"""Is snake's period set by the CONTROLLER's lap or by the DISPLAY's frame?

interp/src/lib.rs releases round R+1's input only once round R has been judged
(`frame_matched >= round_frame_end[R]` for a display-judged problem).  Snake IS
display-judged, so the controller physically cannot start round R+1 until the
display driver has finished rendering round R.  Any controller-side saving
smaller than that slack buys NOTHING.

This measures, per case, how long the controller sits blocked on its head read
-- that stall IS the slack against the display path.

  python3 snake3_pace.py <man>
"""
import collections
import json
import os
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
man = sys.argv[1]
spec = json.load(open(os.path.join(REPO, "tests", "snake.json")))

rows = open(man).read().split("\n")
W = max(len(r) for r in rows)
rows = [r.ljust(W) for r in rows]

caps = {}
g = subprocess.run([sys.executable, os.path.join(REPO, "tools", "grade_fast.py"),
                    "snake", man], capture_output=True, text=True)
d = json.loads(g.stdout.strip().splitlines()[-1])
for r in d["results"]:
    caps[r["name"]] = r["settleTick"]
print(f"box {d['footprint']['box']} avgTicks {d['avgTicks']} score {d['score']:.0f}")

for ci, tc in enumerate(spec["publicTestData"]):
    rs = tc.get("rounds") or [tc]
    inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
    exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
    fr = [r.get("frames") or [] for r in rs]
    ff = f"/tmp/snake3_frames{ci}.json"
    open(ff, "w").write(json.dumps(fr) if any(fr) else "")
    cap = caps[tc["name"]]
    p = subprocess.run([LM, man, "--trace", f"--input={inp}", f"--expected={exp}",
                        f"--frames-file={ff}", f"--cap={cap}"],
                       capture_output=True, text=True)
    tracks = collections.defaultdict(list)
    for line in (p.stdout or "").splitlines():
        parts = line.split("|")
        for wi, seg in enumerate(parts[1:]):
            f = seg.split()
            if len(f) >= 2:
                tracks[wi].append((int(f[0]), int(f[1])))
    best = max(tracks, key=lambda w: sum(
        1 for a, b in zip(tracks[w], tracks[w][1:]) if a != b))
    seq = tracks[best]
    stalls = collections.Counter()
    for a, b in zip(seq, seq[1:]):
        if a == b:
            stalls[a] += 1
    tot = sum(stalls.values())
    top = stalls.most_common(2)
    nrounds = len(rs)
    print(f"case {ci} {tc['name']:24s} ticks {len(seq):6d} rounds {nrounds:3d} "
          f"({len(seq) / nrounds:6.1f}/rnd)  ctrl=w{best} stall {tot:6d} "
          f"({tot / nrounds:5.1f}/rnd, {100 * tot / len(seq):4.1f}%)  "
          + " ".join(f"{c}{rows[c[1]][c[0]]!r}:{n}" for c, n in top))
