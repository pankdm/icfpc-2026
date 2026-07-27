#!/usr/bin/env python3
"""glides.py generalised to any slug: rank pure-travel runs by length x frequency.

sudoku has ~11 concurrent men, so the trace has to be split per man before runs are
accumulated -- otherwise consecutive trace lines belong to different walkers and
every "run" is an artefact.

  python3 sw_glides.py <slug> <man> [top-n] [case-index]

Two corrections that are mandatory on multi-man programs:
  * split the trace PER WALKER, or every "run" is an artefact of interleaved
    trace lines;
  * slack on a man who PARKS on `r` is free -- only the man whose lap IS the
    round period costs ticks.  Check the per-man lap column before acting.
"""
import collections, json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
SLUG = sys.argv[1]
man = sys.argv[2]
topn = int(sys.argv[3]) if len(sys.argv) > 3 else 15
ci = int(sys.argv[4]) if len(sys.argv) > 4 else 0

spec = json.load(open(os.path.join(REPO, "tests", SLUG + ".json")))
tc = spec["publicTestData"][ci]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.run([LM, man, "--trace", "--input=" + inp, "--expected=" + exp,
                    "--cap=5000000"], capture_output=True, text=True)
out = (p.stdout or "")
if not out.strip():
    print("no trace output; stderr:", (p.stderr or "")[:300])
    sys.exit(1)
open("/tmp/r1_trace_sample.txt", "w").write("\n".join(out.splitlines()[:6]))

# Trace line: "<tick> | x y a b bp | x y a b bp | ..." -- one group per man, in
# creation order.  On the valid-grid case no man halts, so group index k is a
# stable identity once the startup forks are done.
per = collections.defaultdict(list)
cellhits = collections.Counter()
nline = 0
for line in out.splitlines():
    q = [t.strip() for t in line.split("|")]
    if len(q) < 2:
        continue
    nline += 1
    for k, g in enumerate(q[1:]):
        f = g.split()
        if len(f) < 2:
            continue
        try:
            x, y = int(f[0]), int(f[1])
        except ValueError:
            continue
        per[k].append((x, y))
        cellhits[(x, y)] += 1

rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]
TURN = set("<>^v")


def isop(x, y):
    if not (0 <= y < len(rows) and 0 <= x < w):
        return True
    ch = rows[y][x]
    return ch != " " and ch not in TURN


runs = collections.Counter()
total = 0
for mid, seq in per.items():
    total += len(seq)
    i = 0
    while i < len(seq):
        if isop(*seq[i]):
            i += 1
            continue
        j = i
        while j < len(seq) and not isop(*seq[j]):
            j += 1
        runs[(seq[i], seq[j - 1], j - i)] += 1
        i = j

scored = sorted(((n * L, L, n, a, b) for (a, b, L), n in runs.items()), reverse=True)
print("trace lines", nline, "men", len(per), "cell-steps", total)
import io
with open("/tmp/r1_walkcounts.txt", "w") as fh:
    for (x, y), n in sorted(cellhits.items(), key=lambda t: -t[1]):
        fh.write("%3d %3d %-3s %d\n" % (x, y, repr(rows[y][x])[1:-1], n))
for cost, L, n, a, b in scored[:topn]:
    print("cost %6d  run %3d cells x%-5d  %s -> %s  glyphs %r" % (
        cost, L, n, a, b, "".join(rows[a[1]][a[0]:a[0] + 1])))
