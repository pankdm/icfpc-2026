"""Find recently committed .man files with no matching submission archive."""
import hashlib, os, subprocess, glob, sys
REPO = '/Users/visenbaev/icfpc26'


def h(p):
    try:
        return hashlib.sha1(open(p, 'rb').read()).hexdigest()
    except Exception:
        return None


sub = {}
for p in glob.glob(REPO + '/submitted/*/*.man'):
    sub.setdefault(h(p), []).append(p)

out = subprocess.run(['git', 'log', '--since=150 minutes ago', '--name-only',
                      '--diff-filter=AM', '--pretty=format:'],
                     cwd=REPO, capture_output=True, text=True).stdout
names = sorted({l.strip() for l in out.split('\n')
                if l.strip().endswith('.man')})
skip = ('scratchpad/hist', 'scratchpad/s4geo')
cands = []
for n in names:
    if any(n.startswith(s) for s in skip):
        continue
    p = os.path.join(REPO, n)
    if not os.path.exists(p):
        continue
    if h(p) in sub:
        continue
    cands.append(n)
print('recent .man:', len(names), ' unsubmitted candidates:', len(cands))
for c in cands:
    print(' ', c)
