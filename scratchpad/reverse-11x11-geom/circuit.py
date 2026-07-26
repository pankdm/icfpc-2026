"""Extract the visited-cell circuit of a .man program: which cells are walked,
by whom, and with what incoming/outgoing direction. Prints a compact map."""
import json, subprocess, sys, collections

LM = "/Users/visenbaev/icfpc26/interp/target/release/lm"

def load(p):
    g = [l.rstrip('\n') for l in open(p)]
    return g

def ch(g, x, y):
    if 0 <= y < len(g) and 0 <= x < len(g[y]):
        return g[y][x]
    return ' '

def main():
    prog = sys.argv[1]; inp = sys.argv[2]; exp = sys.argv[3]; steps = sys.argv[4]
    g = load(prog)
    out = subprocess.run([LM, prog, steps, "--input=" + inp, "--expected=" + exp],
                         capture_output=True, text=True).stdout
    # per-man position sequence
    seq = collections.defaultdict(list)
    for line in out.splitlines():
        j = json.loads(line)
        for r in j["runners"]:
            if r["halted"]:
                continue
            x, y = r["pos"][0], r["pos"][1]
            if not seq[r["id"]] or seq[r["id"]][-1] != (x, y):
                seq[r["id"]].append((x, y))
    visited = set()
    edges = collections.Counter()
    for mid, path in seq.items():
        for i, p in enumerate(path):
            visited.add(p)
            if i + 1 < len(path):
                edges[(p, path[i + 1])] += 1
    xs = [p[0] for p in visited]; ys = [p[1] for p in visited]
    print("men:", len(seq), " visited cells:", len(visited),
          " bbox x %d..%d (%d) y %d..%d (%d)" % (min(xs), max(xs), max(xs)-min(xs)+1,
                                                 min(ys), max(ys), max(ys)-min(ys)+1))
    # map: op char if visited, '.' if in-room but unvisited
    print("visited map (op char, '.' = unvisited interior):")
    for y in range(min(ys), max(ys) + 1):
        row = ""
        for x in range(min(xs), max(xs) + 1):
            c = ch(g, x, y)
            row += (c if (x, y) in visited else ('.' if c == ' ' else c.lower()))
        print("  y%-2d %s" % (y, row))
    # degree analysis
    outdeg = collections.defaultdict(set); indeg = collections.defaultdict(set)
    for (a, b) in edges:
        outdeg[a].add(b); indeg[b].add(a)
    print("branch cells (outdeg>1):", sorted((p, len(v)) for p, v in outdeg.items() if len(v) > 1))
    print("merge cells (indeg>1):", sorted((p, len(v)) for p, v in indeg.items() if len(v) > 1))
    print("unvisited interior count:", sum(1 for y in range(min(ys), max(ys)+1)
                                           for x in range(min(xs), max(xs)+1)
                                           if (x, y) not in visited))

main()
