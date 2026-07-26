"""Union of visited cells across many inputs, plus per-cell visit counts."""
import json, subprocess, sys, collections

LM = "/Users/visenbaev/icfpc26/interp/target/release/lm"

def ch(g, x, y):
    if 0 <= y < len(g) and 0 <= x < len(g[y]):
        return g[y][x]
    return ' '

def runcase(prog, inp, exp, steps):
    out = subprocess.run([LM, prog, str(steps), "--input=" + inp, "--expected=" + exp],
                         capture_output=True, text=True).stdout
    seq = collections.defaultdict(list)
    for line in out.splitlines():
        j = json.loads(line)
        for r in j["runners"]:
            if r["halted"]:
                continue
            x, y = r["pos"][0], r["pos"][1]
            if not seq[r["id"]] or seq[r["id"]][-1] != (x, y):
                seq[r["id"]].append((x, y))
    vis = collections.Counter()
    edges = collections.Counter()
    for mid, path in seq.items():
        for i, p in enumerate(path):
            vis[p] += 1
            if i + 1 < len(path):
                edges[(p, path[i + 1])] += 1
    return vis, edges

def main():
    prog = sys.argv[1]
    g = [l.rstrip('\n') for l in open(prog)]
    cases = []
    for n in range(1, 17):
        vals = list(range(1, n + 1))
        cases.append((" ".join(str(v) for v in [n] + vals),
                      " ".join(str(v) for v in reversed(vals))))
    # multi-round
    cases.append(("3 1 2 3 / 4 5 6 7 8 / 1 9", "3 2 1 / 8 7 6 5 / 9"))
    cases.append(("2 1 2 / 15 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15",
                  "2 1 / 15 14 13 12 11 10 9 8 7 6 5 4 3 2 1"))
    tot = collections.Counter(); alledges = collections.Counter()
    for inp, exp in cases:
        v, e = runcase(prog, inp, exp, 400)
        tot.update(v); alledges.update(e)
    visited = set(tot)
    # all non-space cells inside rooms
    nonspace = set()
    for y, l in enumerate(g):
        for x, c in enumerate(l):
            if c not in ' ':
                nonspace.add((x, y))
    xs = [p[0] for p in visited]; ys = [p[1] for p in visited]
    print("visited %d cells, bbox x %d..%d (w=%d) y %d..%d (h=%d)" % (
        len(visited), min(xs), max(xs), max(xs)-min(xs)+1, min(ys), max(ys), max(ys)-min(ys)+1))
    print("map: op char if visited (uppercase kept), '~' nonspace-unvisited, '.' space-unvisited")
    for y in range(min(ys)-1, max(ys)+2):
        row = ""
        for x in range(min(xs)-1, max(xs)+2):
            c = ch(g, x, y)
            if (x, y) in visited:
                row += c if c != ' ' else '_'
            else:
                row += '~' if c not in ' ' else '.'
        print("  y%-2d %s" % (y, row))
    print("visit counts (low-traffic first):")
    for p, c in sorted(tot.items(), key=lambda kv: kv[1])[:20]:
        print("   ", p, ch(g, *p), c)
    print("nonspace-but-never-visited inside bbox:",
          sorted(p for p in nonspace - visited
                 if min(xs)-1 <= p[0] <= max(xs)+1 and min(ys)-1 <= p[1] <= max(ys)+1))
    # dump graph edges for the reachable circuit
    with open(sys.argv[2], "w") as f:
        json.dump({"visited": sorted(map(list, visited)),
                   "edges": [[list(a), list(b), c] for (a, b), c in alledges.items()],
                   "ops": {"%d,%d" % p: ch(g, *p) for p in visited}}, f)

main()
