#!/usr/bin/env python3
"""Split the controller's round into A (before the display send) and B (after).

Round R+1's input is released only once round R is judged, so with
    A = ticks from the head read to the display send
    B = ticks from the display send back to the head
    C = release latency from the display send
the period is  A + max(B, C).  Savings in A pay 1:1; savings in B pay NOTHING
until B exceeds C -- and the measured idle (C - B) is how much work could be
MOVED from A into B for free.

  python3 snake3_phase.py <man> [case]
"""
import collections
import json
import os
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
man = sys.argv[1]
case = int(sys.argv[2]) if len(sys.argv) > 2 else 4

spec = json.load(open(os.path.join(REPO, "tests", "snake.json")))
tc = spec["publicTestData"][case]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
fr = [r.get("frames") or [] for r in rs]
ff = "/tmp/snake3_phase_frames.json"
open(ff, "w").write(json.dumps(fr) if any(fr) else "")

g = subprocess.run([sys.executable, os.path.join(REPO, "tools", "grade_fast.py"),
                    "snake", man], capture_output=True, text=True)
d = json.loads(g.stdout.strip().splitlines()[-1])
cap = [r["settleTick"] for r in d["results"] if r["name"] == tc["name"]][0]

p = subprocess.run([LM, man, "--trace", f"--input={inp}", f"--expected={exp}",
                    f"--frames-file={ff}", f"--cap={cap}"],
                   capture_output=True, text=True)
rows = open(man).read().split("\n")
W = max(len(r) for r in rows)
rows = [r.ljust(W) for r in rows]

tracks = collections.defaultdict(list)
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    for wi, seg in enumerate(parts[1:]):
        f = seg.split()
        if len(f) >= 2:
            tracks[wi].append((int(f[0]), int(f[1])))

ctrl = max(tracks, key=lambda w: sum(
    1 for a, b in zip(tracks[w], tracks[w][1:]) if a != b))
seq = tracks[ctrl]
# The head = the cell the controller blocks on longest and leaves exactly once
# per round.
stalls = collections.Counter()
for a, b in zip(seq, seq[1:]):
    if a == b:
        stalls[a] += 1
head = stalls.most_common(1)[0][0]

# Ticks where the controller LEAVES the head (one per round).
leaves = [t for t in range(len(seq) - 1) if seq[t] == head and seq[t + 1] != head]
# Every `s` the controller executes, per round, with its position in the lap.
sends = collections.Counter()
for t, c in enumerate(seq):
    if rows[c[1]][c[0]] == "s":
        sends[c] += 1
print(f"{tc['name']}: {len(seq)} ticks, controller = walker {ctrl}, head {head}")
print(f"  {len(leaves)} rounds, mean period {len(seq) / max(len(leaves), 1):.1f}")

# For each send cell, mean offset from the round start -- the LAST distinct send
# before the next head arrival is the one the release waits on.
starts = leaves
print("  send cell           count   mean offset in round   (A side if small)")
for c, n in sends.most_common(12):
    offs = []
    for t, cc in enumerate(seq):
        if cc != c:
            continue
        k = max([i for i, s in enumerate(starts) if s <= t], default=None)
        if k is not None:
            offs.append(t - starts[k])
    if offs:
        print(f"    {str(c):14s} {rows[c[1]][c[0]]!r} {n:5d}   "
              f"mean {sum(offs) / len(offs):6.1f}  max {max(offs):5d}")
arrive = []
for k, s in enumerate(starts[:-1]):
    nxt = next((t for t in range(s + 1, len(seq)) if seq[t] == head), None)
    if nxt is not None:
        idle = 0
        t = nxt
        while t + 1 < len(seq) and seq[t + 1] == head:
            idle += 1
            t += 1
        arrive.append((nxt - s, idle))
if arrive:
    ab = sum(a for a, _ in arrive) / len(arrive)
    idl = sum(i for _, i in arrive) / len(arrive)
    print(f"  controller work per round {ab:6.1f}   idle at head {idl:6.1f}"
          f"   period {ab + idl:6.1f}")
    print(f"  => up to {idl:.1f} ticks/round ({100 * idl / (ab + idl):.1f}%) could be "
          f"moved from before the display send to after it, for free")
