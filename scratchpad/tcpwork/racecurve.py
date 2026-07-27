#!/usr/bin/env python3
"""Turn the read-loop pass/fail scan into a CURVE, and measure the race in ticks.

bxdecode's main man ends his loop at the `Y`; the spawned copy is born facing
EAST on row 3, glides east to a turn-around column, goes north and comes back
west on row 1 to the `r` at (10,2). That detour is a DELAY: it holds the main man
back so the CLONE reads `val` (the `r` row) before he reads the next `seq` off
the shared input FIFO.

Part 1 sweeps the turn-around column and records avgTicks AND per-case pass/fail,
so a soft cliff (some cases failing before others) is visible instead of being
inferred from one sample.

Part 2 measures the actual slack in TICKS: it replays the engine one tick at a
time, watches `inputRead` increment, and attributes each read to the runner
standing on an `r` cell that tick. The gap we care about is
    tick(main man reads seq_{k+1}) - tick(clone reads val_k)
which must stay > 0. Columns tell you nothing about how many ticks that is.
"""
import json
import subprocess
import sys

REPO = '/Users/visenbaev/icfpc26'
SRC = f'{REPO}/solutions/tcp/bxdecode-23x23.man'
LM = f'{REPO}/interp/target/release/lm'
GRADE = f'{REPO}/tools/grade_fast.py'
TURN_ROW_N, TURN_ROW_S = 1, 3          # '<' on row 1, '^' on row 3
BASE_COL = 16


def load():
    rows = open(SRC).read().rstrip('\n').split('\n')
    w = max(len(r) for r in rows)
    return [list(r.ljust(w)) for r in rows]


def variant(k, path):
    g = load()
    assert g[TURN_ROW_N][BASE_COL] == '<', g[TURN_ROW_N][BASE_COL]
    assert g[TURN_ROW_S][BASE_COL] == '^', g[TURN_ROW_S][BASE_COL]
    g[TURN_ROW_N][BASE_COL] = ' '
    g[TURN_ROW_S][BASE_COL] = ' '
    g[TURN_ROW_N][k] = '<'
    g[TURN_ROW_S][k] = '^'
    open(path, 'w').write('\n'.join(''.join(r).rstrip() for r in g) + '\n')
    return path


def cases():
    spec = json.load(open(f'{REPO}/tests/tcp.json'))
    for tc in spec['publicTestData']:
        rs = tc['rounds']
        yield (tc['name'],
               ' / '.join(' '.join(r['in']) for r in rs),
               ' / '.join(' '.join(r.get('out') or []) for r in rs))


def sweep():
    print('col  ticks     verdict   per-case')
    for k in range(11, 21):
        p = variant(k, f'/tmp/rc_{k}.man')
        out = subprocess.run([sys.executable, GRADE, 'tcp', p],
                             capture_output=True, text=True).stdout.strip().splitlines()
        v = json.loads(out[-1])
        marks = ''.join('.' if r['status'] == 'pass' else 'X' for r in v['results'])
        print(f"{k:3d}  {str(v.get('avgTicks')):9s} {v['passed']}/{v['total']}   {marks}")


def slack(k, case_name='block-reversed', steps=1200):
    """Replay tick-by-tick and report the val-read -> next-seq-read gap in TICKS.

    A runner executed the cell it stood on in the PREVIOUS snapshot, and it only
    actually performed a blocking `r` on the step where it finally MOVES OFF that
    cell -- a blocked man sits on the `r` for as many ticks as it waits, so
    attributing the read to the first tick would overstate the slack.
    """
    p = variant(k, f'/tmp/rc_slack_{k}.man')
    grid = open(p).read().rstrip('\n').split('\n')

    def at(x, y):
        return grid[y][x] if 0 <= y < len(grid) and 0 <= x < len(grid[y]) else ' '

    name, inp, exp = next(c for c in cases() if case_name in c[0])
    proc = subprocess.run([LM, p, str(steps), f'--input={inp}'],
                          capture_output=True, text=True)
    snaps = []
    for line in proc.stdout.splitlines():
        try:
            snaps.append(json.loads(line))
        except ValueError:
            pass
    reads = []                                   # (tick, row_of_r_cell)
    for n in range(1, len(snaps)):
        prev = {r['id']: tuple(r['pos']) for r in snaps[n - 1]['runners']}
        cur = {r['id']: tuple(r['pos']) for r in snaps[n]['runners']}
        for rid, pos in prev.items():
            if rid in cur and cur[rid] != pos and at(pos[0], pos[1]) == 'r':
                reads.append((snaps[n]['step'], pos[1]))
    seq_row = min(r for _, r in reads) if reads else None
    gaps = []
    for i in range(1, len(reads)):
        (t0, r0), (t1, r1) = reads[i - 1], reads[i]
        if r0 != seq_row and r1 == seq_row:       # val read, then the next seq read
            gaps.append(t1 - t0)
    print(f"col {k}: reads={len(reads)} seq_row={seq_row} "
          f"val->next-seq gap ticks: min={min(gaps) if gaps else None} "
          f"max={max(gaps) if gaps else None} n={len(gaps)}")


if __name__ == '__main__':
    if sys.argv[1:] and sys.argv[1] == 'slack':
        for k in (16, 15, 14):
            slack(k)
    else:
        sweep()


def slack_all():
    """Global worst-case slack: the clone's path length varies with the SLOT, so
    the true floor only shows once every decode path has been exercised."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'stress', f'{REPO}/scratchpad/tcpwork/stress.py')
    worst = None
    for name, inp, exp in cases():
        g = _gaps(16, inp)
        if g:
            lo = min(g)
            worst = lo if worst is None else min(worst, lo)
            print(f"  {name:28s} packets={len(g):3d} min_gap={lo}")
    print('GLOBAL MIN SLACK (public):', worst, 'ticks')


def _gaps(k, inp, steps=4000):
    p = variant(k, f'/tmp/rc_g{k}.man')
    grid = open(p).read().rstrip('\n').split('\n')
    at = lambda x, y: grid[y][x] if 0 <= y < len(grid) and 0 <= x < len(grid[y]) else ' '
    proc = subprocess.run([LM, p, str(steps), f'--input={inp}'],
                          capture_output=True, text=True)
    snaps = []
    for line in proc.stdout.splitlines():
        try:
            snaps.append(json.loads(line))
        except ValueError:
            pass
    reads = []
    for n in range(1, len(snaps)):
        prev = {r['id']: tuple(r['pos']) for r in snaps[n - 1]['runners']}
        cur = {r['id']: tuple(r['pos']) for r in snaps[n]['runners']}
        for rid, pos in prev.items():
            if rid in cur and cur[rid] != pos and at(pos[0], pos[1]) == 'r':
                reads.append((snaps[n]['step'], pos[1]))
    if not reads:
        return []
    sr = min(r for _, r in reads)
    return [t1 - t0 for (t0, r0), (t1, r1) in zip(reads, reads[1:])
            if r0 != sr and r1 == sr]
