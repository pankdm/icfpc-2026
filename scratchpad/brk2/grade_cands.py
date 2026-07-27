import json, subprocess, sys, os
R = '/Users/visenbaev/icfpc26'
LIVE = {
    'brackets': 81782, 'gradebook': 105095168, 'history-lesson': 6400,
    'matmul': 26899171, 'memory': 5756282, 'plotter': 4516500,
    'snake': 39163576, 'sort-numbers': 262915, 'subset-sum': 2286010829,
    'sudoku-validity': 1670038, 'tcp': 314600, 'reverse-a-list': 13764,
    'triangle': 832, 'little-little-man': 2855611349284,
    'little-little-little-man': 6282959332,
}
CAND = [
    ('gradebook', 'gradebook-walkfold.man'),
    ('plotter', 'plotter-tight31-polished.man'),
    ('sudoku-validity', 'ringfree4-tuned-peep.man'),
    ('sudoku-validity', 'multi2-tuned.man'),
    ('tcp', 'x3-23x23.man'),
    ('tcp', 'x2-23x23.man'),
    ('memory', 'direct-memory-k25-blocks.man'),
    ('memory', 'rewind-narrow.man'),
    ('sort-numbers', 'v1_16x16.man'),
    ('reverse-a-list', 'repack11.man'),
    ('triangle', 'weave8x8.man'),
    ('matmul', 'matmul-tight2.man'),
    ('snake', 'linked-compact-reflow-s16-sb4-cb8-cx10-o0.man'),
    ('little-little-man', 'pipe-io-banked-dedup-rowfold.man'),
]
for slug, f in CAND:
    p = os.path.join(R, 'solutions', slug, f)
    if not os.path.exists(p):
        print('%-18s %-46s MISSING' % (slug, f)); continue
    try:
        r = subprocess.run(['python3', R + '/tools/grade_fast.py', slug, p],
                           capture_output=True, text=True, timeout=240, cwd=R)
        d = json.loads(r.stdout.strip().split('\n')[-1])
    except Exception as e:
        print('%-18s %-46s ERR %s' % (slug, f, str(e)[:30])); continue
    sc = d.get('score')
    live = LIVE.get(slug)
    tag = ''
    if d['passed'] == d['total'] and sc and live and sc < live:
        tag = '  <<< BEATS LIVE %.3fx' % (live / sc)
    print('%-18s %-46s %d/%d %s%s' % (slug, f, d['passed'], d['total'],
                                      ('%.0f' % sc) if sc else '-', tag))
    sys.stdout.flush()
