"""Extract per-tick man positions from lm --trace; write annotated path."""
import json, subprocess, sys
REPO = '/Users/visenbaev/icfpc26'
LM = REPO + '/interp/target/release/lm'
cases = json.load(open(REPO + '/scratchpad/brk2/cases.json'))
prog = sys.argv[1] if len(sys.argv) > 1 else REPO + '/solutions/brackets/p5v2.man'
ci = int(sys.argv[2]) if len(sys.argv) > 2 else 8
t0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0
t1 = int(sys.argv[4]) if len(sys.argv) > 4 else 200
which = sys.argv[5] if len(sys.argv) > 5 else 'all'
c = cases[ci]
r = subprocess.run([LM, prog, '--trace', '--cap=4000',
                    '--input=' + ' '.join(c['in']), '--expected=' + ' '.join(c['out'])],
                   capture_output=True, text=True)
lines = [l for l in r.stdout.split('\n') if l.strip()]
grid = open(prog).read().split('\n')
def ch(x, y):
    return grid[y][x] if y < len(grid) and x < len(grid[y]) else '?'
out = []
for l in lines[t0:t1]:
    f = l.split('|')
    st = f[0].strip()
    parts = []
    for i, m in enumerate(f[1:]):
        x, y, a, b, bp = m.split()
        x, y = int(x), int(y)
        parts.append('%2d,%2d %s A%s B%s P%s' % (x, y, ch(x, y), a, b, bp))
    if which != 'all':
        parts = [parts[int(which)]]
    out.append('%5s %s' % (st, ' | '.join(parts)))
p = REPO + '/scratchpad/brk2/trace_%d_%d.txt' % (ci, t0)
open(p, 'w').write('\n'.join(out) + '\n')
print('lines', len(lines), '->', p)
