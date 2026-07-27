#!/usr/bin/env python3
"""Find the dominant walk cycles of man0 from an lm --trace.

For every cell, take the gaps between consecutive visits; the modal gap is the
loop body length and (count * gap) is the ticks that loop owns.  Report the
loops, deduplicated by body, biggest first, with the ops on the body.

  python3 scratchpad/gbrelayout/loops.py <man> [case-index] [top-n]
"""
import collections, json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

man = sys.argv[1]
idx = int(sys.argv[2]) if len(sys.argv) > 2 else -1
topn = int(sys.argv[3]) if len(sys.argv) > 3 else 12

spec = json.load(open(os.path.join(REPO, "tests", "gradebook.json")))
tc = spec["publicTestData"][idx]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)

p = subprocess.run([LM, man, "--trace", f"--input={inp}", f"--expected={exp}", "--cap=5000000"],
                   capture_output=True, text=True)
seq = []
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    if len(parts) < 2:
        continue
    f2 = parts[1].split()
    if len(f2) >= 2:
        seq.append((int(f2[0]), int(f2[1])))
print("trace ticks", len(seq))

rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]

pos = collections.defaultdict(list)
for t, c in enumerate(seq):
    pos[c].append(t)

loops = []
for c, ts in pos.items():
    if len(ts) < 5:
        continue
    gaps = collections.Counter(ts[i + 1] - ts[i] for i in range(len(ts) - 1))
    g, n = gaps.most_common(1)[0]
    if g < 3 or n < 4:
        continue
    # body = cells visited in one representative iteration
    for i in range(len(ts) - 1):
        if ts[i + 1] - ts[i] == g:
            body = seq[ts[i]:ts[i + 1]]
            break
    loops.append((n * g, g, n, c, tuple(sorted(set(body)))))

loops.sort(reverse=True)
seen = set()
shown = 0
for cost, g, n, c, body in loops:
    key = body
    if key in seen:
        continue
    seen.add(key)
    ops = [(x, y, rows[y][x]) for (x, y) in body if rows[y][x] not in " "]
    xs = [x for x, y in body]
    ys = [y for x, y in body]
    print("cost %6d  len %3d  x%-4d anchor %s  cols %d-%d rows %d-%d  ops %d: %s"
          % (cost, g, n, c, min(xs), max(xs), min(ys), max(ys), len(ops),
             "".join(o[2] for o in ops)))
    print("      ", " ".join("%d,%d%s" % o for o in ops))
    shown += 1
    if shown >= topn:
        break
