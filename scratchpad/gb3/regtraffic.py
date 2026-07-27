#!/usr/bin/env python3
"""regtraffic.py <man> [case] [steps] — how often man0 executes each r/s/q, grouped by bound pipe."""
import json, subprocess, sys, os, collections
REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

man = sys.argv[1]
sub = sys.argv[2] if len(sys.argv) > 2 else "N=16"
steps = int(sys.argv[3]) if len(sys.argv) > 3 else 40000
rows = wf.load_rows(man)
g = wf.Grid(rows)
tab, pure, inc, out = wf.bands(g, 0)
inpos = dict(inc); outpos = dict(out)

d = json.load(open("tests/gradebook.json"))
c = [x for x in d["publicTestData"] if sub in x["name"]][0]
rs = c["rounds"]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.Popen(["interp/target/release/lm", man, str(steps), "--input=" + inp,
                      "--expected=" + exp, "--cap=3000000"],
                     stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
visits = collections.Counter()
prev = None
for line in p.stdout:
    try:
        o = json.loads(line)
    except Exception:
        continue
    r = o["runners"][0]
    pos = tuple(r["pos"]) if isinstance(r.get("pos"), list) else (r.get("x"), r.get("y"))
    if pos != prev:
        visits[pos] += 1
    prev = pos
p.stdout.close(); p.wait()

(x0, y0), (x1, y1) = g.rooms[0]["min"], g.rooms[0]["max"]
per = collections.Counter()
detail = collections.defaultdict(list)
for y in range(y0 + 1, y1):
    for x in range(x0 + 1, x1):
        ch = g.at(x, y)
        if ch not in "rsq":
            continue
        kind = "out" if ch == "s" else "in"
        pi = tab[x][kind]
        v = visits[(x, y)]
        per[(kind, pi)] += v
        detail[(kind, pi)].append((x, y, ch, v))
print(f"pipe attach cols: in {sorted((c[0], pi) for pi, c in inc)}  out {sorted((c[0], pi) for pi, c in out)}")
for k in sorted(per, key=lambda k: -per[k]):
    kind, pi = k
    col = (inpos if kind == "in" else outpos)[pi][0]
    print(f" {kind} pipe{pi} @col{col}: {per[k]:6d} exec   " +
          " ".join(f"{ch}({x},{y})x{v}" for x, y, ch, v in sorted(detail[k], key=lambda t: -t[3])[:8]))
