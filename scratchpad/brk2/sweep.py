"""Random sweep: find shapes where p6v1 is slower than p5v2."""
import random, sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/scratchpad/brk2')
from stress import run, bal, PAIR, O, Cl, A, B

random.seed(11)
CH = '([{'
rows = []
for trial in range(60):
    nr = random.choice([1, 1, 2, 3, 5])
    rounds = []
    for _ in range(nr):
        n = random.choice([0, 1, 2, 3, 4, 6, 8, 12, 20, 32, 48, 64])
        kind = random.choice(['bal', 'bal', 'open', 'close', 'off'])
        if n == 0:
            s = ''
        elif kind == 'bal':
            s = bal(n - n % 2, random.choice([CH, '(', '[', '{']))
        elif kind == 'open':
            s = ''.join(random.choice(CH) for _ in range(n))
        elif kind == 'close':
            s = ''.join(random.choice(')]}') for _ in range(n))
        else:
            b = bal(n - n % 2)
            i = random.randrange(len(b)) if b else 0
            s = b[:i] + random.choice(')]}') + b[i + 1:] if b else ''
        rounds.append(s)
    sa, ta = run(A, rounds)
    sb, tb = run(B, rounds)
    if sa != 'pass' or sb != 'pass':
        continue
    rows.append((tb / max(ta, 1), ta, tb, [len(r) for r in rounds]))
rows.sort(reverse=True)
print('worst ratios (p6/p5):')
for r in rows[:12]:
    print('  %.2f  p5=%5d p6=%5d  lens=%s' % r)
print('n=%d  mean ratio %.3f' % (len(rows), sum(r[0] for r in rows) / len(rows)))
