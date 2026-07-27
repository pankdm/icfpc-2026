"""Profile one brackets case; write compact per-cell overlay to a file."""
import json, subprocess, sys, ast, re, os
REPO = '/Users/visenbaev/icfpc26'
LM = REPO + '/interp/target/release/lm'
cases = json.load(open(REPO + '/scratchpad/brk2/cases.json'))

prog = sys.argv[1] if len(sys.argv) > 1 else REPO + '/solutions/brackets/p5v2.man'
ci = int(sys.argv[2]) if len(sys.argv) > 2 else 8
c = cases[ci]
r = subprocess.run([LM, '--profile', '--grade', prog,
                    '--input=' + ' '.join(c['in']), '--expected=' + ' '.join(c['out'])],
                   capture_output=True, text=True)
print(r.stdout.strip())
err = r.stderr
def grab(tag):
    m = re.search(r'PROFILE ' + tag + r'=(.*)', err)
    return m.group(1) if m else None
cells = ast.literal_eval(grab('cells'))
stalls = ast.literal_eval(grab('stalls') or '[]')
stall_total = grab('stall_total')
cellmap = dict(cells)
stallmap = dict(stalls)
print('exec_total', sum(cellmap.values()), 'stall_total', stall_total)
print('glyphs', grab('glyphs'))

rows = open(prog).read().split('\n')
out = []
tot = sum(cellmap.values()) + sum(stallmap.values())
for y, row in enumerate(rows):
    for x, ch in enumerate(row):
        e = cellmap.get((x, y), 0)
        s = stallmap.get((x, y), 0)
        if e or s:
            out.append((e + s, e, s, x, y, ch))
out.sort(reverse=True)
with open(REPO + '/scratchpad/brk2/prof_%d.txt' % ci, 'w') as f:
    f.write('case %s ticks-ish total=%d\n' % (c['name'], tot))
    f.write('tot exec stall  x  y ch\n')
    for t, e, s, x, y, ch in out:
        f.write('%4d %4d %5d %2d %2d %s\n' % (t, e, s, x, y, ch))
print('wrote prof_%d.txt, %d live cells' % (ci, len(out)))
