"""Rank the blank-glide cost of a .man on a snake case, grouped into runs."""
import ast, json, subprocess, sys
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
cells = None
for line in out.stderr.splitlines():
    if line.startswith("PROFILE cells="):
        cells = dict(ast.literal_eval(line.split("=", 1)[1]))
rows = open(man).read().split("\n")
def ch(x, y):
    r = rows[y] if y < len(rows) else ""
    return r[x] if x < len(r) else " "

blank = {p: n for p, n in cells.items() if ch(*p) == " "}
print("total blank ticks", sum(blank.values()), "of", sum(cells.values()))
# group into horizontal runs
seen = set()
runs = []
for (x, y), n in sorted(blank.items(), key=lambda kv: -kv[1]):
    if (x, y) in seen:
        continue
    xs = [x]
    a = x - 1
    while (a, y) in blank and (a, y) not in seen:
        xs.append(a); a -= 1
    b = x + 1
    while (b, y) in blank and (b, y) not in seen:
        xs.append(b); b += 1
    for xx in xs:
        seen.add((xx, y))
    tot = sum(blank[(xx, y)] for xx in xs)
    runs.append((tot, y, min(xs), max(xs), len(xs)))
runs.sort(reverse=True)
for tot, y, x0, x1, ln in runs[:30]:
    print("row %3d cols %3d-%-3d len %2d  ticks %6d" % (y, x0, x1, ln, tot))
# vertical
print("--- by row ---")
byrow = {}
for (x, y), n in blank.items():
    byrow[y] = byrow.get(y, 0) + n
for y, n in sorted(byrow.items(), key=lambda kv: -kv[1])[:20]:
    print("row %3d  %6d" % (y, n))
