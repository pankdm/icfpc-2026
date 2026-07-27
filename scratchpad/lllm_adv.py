#!/usr/bin/env python3
"""Adversarial generality suite for LLLM (slug little-little-little-man).

Oracle = solutions/little-little-little-man/lllm_model.py (validated 116/116 public rounds).
Writes tests/lllm-adv.json (in-spec cases) and tests/lllm-oos.json (deliberately
out-of-spec cases) in the same envelope grade_fast.py reads.

IN-SPEC per tests/little-little-little-man.json "io".constraints:
    4 <= W,H <= 16 | 1 <= k <= 64 | <=30 rounds | <=200 ticks per case
    no step commands arrive after the program halts
"""
import json
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'little-little-little-man'))
import lllm_model as MOD  # noqa: E402

OPS = '^>v<0123456789M+-X'


def framed(W, H, fill):
    """Well-formed program: one room == the whole W x H grid."""
    rows = ['+' + '-' * (W - 2) + '+']
    for y in range(1, H - 1):
        rows.append('|' + ''.join(fill(x, y) for x in range(1, W - 1)) + '|')
    rows.append('+' + '-' * (W - 2) + '+')
    return rows


def from_art(art):
    """Rows given literally (already include the walls).

    Ragged art is a BUG in the test, not a test: padding a short row with a
    space punches a hole in the east wall and the program is no longer
    well-formed.  Refuse it loudly.
    """
    w = max(len(r) for r in art)
    bad = [i for i, r in enumerate(art) if len(r) != w]
    if bad:
        raise AssertionError('ragged art rows %s (width %d): %r' % (bad, w, art))
    return list(art)


def make_case(name, rows, ks, allow_post_halt=False, note=''):
    W = len(rows[0])
    H = len(rows)
    assert all(len(r) == W for r in rows), name
    assert sum(r.count('@') for r in rows) == 1, 'need exactly one @: ' + name
    values = [str(ord(c)) for r in rows for c in r]

    grid = MOD.parse_program([int(v) for v in values], W, H)
    st = MOD.initial_state(grid)
    rounds = [{'in': [str(W), str(H)] + values,
               'frames': [MOD.frame_lines(MOD.frame(grid, st.man))], 'out': []}]
    used = []
    for k in ks:
        if st.halted and not allow_post_halt:
            break                      # spec: no step commands after the halt
        MOD.run_ticks(st, k)
        used.append(k)
        rounds.append({'in': [str(k)],
                       'frames': [MOD.frame_lines(MOD.frame(grid, st.man))], 'out': []})
    return {'name': name, 'rounds': rounds,
            '_meta': {'W': W, 'H': H, 'ks': used, 'ticks': sum(used),
                      'halted': st.halted, 'note': note, 'rows': rows}}


def blank(W, H, at=(1, 1), ch='@'):
    return framed(W, H, lambda x, y: ch if (x, y) == at else ' ')


cases = []
oos = []
A = cases.append


# ---------------------------------------------------------------- boundaries
A(make_case('min4-blank', blank(4, 4), [1] * 4, note='smallest legal room, empty'))
A(make_case('min4-ops', from_art(['+--+', '|@v|', '| H|', '+--+']), [1] * 5,
            note='4x4 with a turn and a halt'))
A(make_case('wide16x4', framed(16, 4, lambda x, y: '@' if (x, y) == (1, 1) else
                               ('>' if y == 1 else ' ')), [1, 2, 3, 9],
            note='max width, min height'))
A(make_case('tall4x16', framed(4, 16, lambda x, y: '@' if (x, y) == (1, 1) else
                               ('v' if x == 1 else ' ')), [1, 2, 3, 12],
            note='min width, max height'))

# full 16x16, every op class present and reachable
full = []
for y in range(16):
    row = []
    for x in range(16):
        if y in (0, 15) or x in (0, 15):
            row.append('+' if x in (0, 15) and y in (0, 15) else
                       ('-' if y in (0, 15) else '|'))
        else:
            row.append(' ')
    full.append(row)
lay = {(1, 1): '@', (2, 1): '1', (3, 1): 'M', (4, 1): '9', (5, 1): '>',
       (6, 1): '-', (13, 1): 'X', (13, 8): '<', (4, 8): '^'}
for (x, y), c in lay.items():
    full[y][x] = c
A(make_case('full16-victorylap', [''.join(r) for r in full], [64, 64, 30, 64],
            note='16x16 victory-lap shape: arithmetic, X, a long lap, then a wall halt'))

# a genuine 16x16 forever-lap: 14-cell ring, man never halts
ring16 = ['+' + '-' * 14 + '+', '|>@' + '>' * 11 + 'v|'] + \
         ['|^' + ' ' * 12 + 'v|' for _ in range(12)] + \
         ['|^' + '<' * 12 + '<|', '+' + '-' * 14 + '+']
A(make_case('full16-forever', from_art(ring16), [64, 64, 64],
            note='16x16, never halts in 192 ticks, revisits the vacated @'))


# ------------------------------------------------------- halting / wall hits
A(make_case('halt-tick1', from_art(['+--+', '| @|', '|  |', '+--+']), [1, 1],
            note='man is adjacent to the east wall: halts on the very first tick'))
A(make_case('halt-H-tick2', from_art(['+---+', '|@H |', '|   |', '+---+']), [1, 1, 1],
            note='H reached on tick 2; man parks on the H forever'))
A(make_case('halt-H-first-cell', from_art(['+----+', '|@   |', '|H   |', '|    |',
                                           '+----+']), [1, 1, 1, 1],
            note='H under the start, reached after a turn'))

# four wall directions, each ending on a different wall
A(make_case('wall-east', from_art(['+----+', '|@   |', '|    |', '+----+']), [1, 2, 3],
            note='ends on the EAST wall'))
A(make_case('wall-north', from_art(['+----+', '|@^  |', '|    |', '+----+']), [1, 2],
            note='ends on the NORTH wall'))
A(make_case('wall-south', from_art(['+----+', '|@v  |', '|    |', '+----+']), [1, 2, 3],
            note='ends on the SOUTH wall'))
A(make_case('wall-west', from_art(['+----+', '|@<  |', '|    |', '+----+']), [1, 2, 3],
            note='ends on the WEST wall'))
A(make_case('wall-corner-ne', from_art(['+----+', '|@ >^|', '|    |', '+----+']),
            [1, 2, 3, 4], note='last interior column then north: parks on the top wall'))
A(make_case('wall-corner-sw', from_art(['+----+', '|@   |', '|<  v|', '|    |', '+----+']),
            [1, 1, 1, 1, 1, 1, 1], note='walks the west wall low down'))

# start adjacent to each wall
A(make_case('start-hug-north', framed(6, 6, lambda x, y: '@' if (x, y) == (2, 1) else ' '),
            [1, 2, 3], note='start on the first interior row'))
A(make_case('start-hug-south', framed(6, 6, lambda x, y: '@' if (x, y) == (2, 4) else ' '),
            [1, 2, 3], note='start on the last interior row'))
A(make_case('start-hug-west', framed(6, 6, lambda x, y: '@' if (x, y) == (1, 3) else ' '),
            [1, 2, 3], note='start on the first interior column'))
A(make_case('start-hug-east', framed(6, 6, lambda x, y: '@' if (x, y) == (4, 3) else ' '),
            [1], note='start on the last interior column: halts on tick 1'))

# never halts: a tight lap the man runs forever, revisiting the vacated '@'
#   the '@' must sit INSIDE a straight run, never on a corner: the vacated cell
#   is a no-op, so a corner turn placed there would walk the man into the wall.
lap = ['+' + '-' * 6 + '+', '|>@' + '>' * 3 + 'v|'] + \
      ['|^' + ' ' * 4 + 'v|' for _ in range(4)] + \
      ['|^' + '<' * 4 + '<|', '+' + '-' * 6 + '+']
A(make_case('lap-forever', from_art(lap), [64, 64, 64],
            note='never halts; man walks back over the vacated @ every lap'))


# -------------------------------------------------------------- op semantics
# X with A > 0, A = 0, A < 0 all exercised on the same run
A(make_case('X-positive', from_art(['+------+', '|@1X   |', '|      |', '|      |',
                                    '|      |', '+------+']), [1, 1, 1, 1, 1, 1],
            note='A=1 then X: clockwise (east -> south)'))
A(make_case('X-zero', from_art(['+------+', '|@0X   |', '|      |', '+------+']),
            [1, 1, 1, 1, 1], note='A=0 then X: no turn'))
A(make_case('X-negative', from_art(['+------+', '|      |', '|@1M0-X|', '|      |',
                                    '|      |', '+------+']), [1, 1, 1, 1, 1, 1, 1],
            note='A = 0-1 = -1 then X: counter-clockwise (east -> north)'))
A(make_case('X-chain', from_art(['+-------+', '|@2M2-X |', '|       |', '|  9X   |',
                                 '|       |', '|       |', '+-------+']),
            [1] * 12, note='A=0 X (straight) then A=9 X (clockwise)'))

# all ten digits executed
dig = ['+' + '-' * 11 + '+', '|@0123456789|', '|' + ' ' * 11 + '|',
       '+' + '-' * 11 + '+']
A(make_case('digits-0-9', from_art(dig), [1] * 13,
            note='every digit 0-9 executed in one run'))

# arithmetic: big positive, big negative, M/W interaction
A(make_case('arith-grow', from_art(['+-----------+', '|@9M++++++++|', '|           |',
                                    '+-----------+']), [1] * 12,
            note='A climbs 9,18,...,81 (colour is unaffected, but the man must not stall)'))
A(make_case('arith-negative', from_art(['+-----------+', '|@9M0-------|',
                                        '|           |', '+-----------+']), [1] * 12,
            note='A dives 0,-9,-18,... : negative A held across ticks'))
A(make_case('arith-then-X', from_art(['+---------+', '|@9M0--X  |', '|         |',
                                      '|         |', '|         |', '+---------+']),
            [1] * 10, note='A = -18 then X turns counter-clockwise'))

# every op class in a single program
allops = ['+' + '-' * 13 + '+',
          '|@1M9+-X<>^v H|',
          '|' + ' ' * 13 + '|',
          '|' + ' ' * 13 + '|',
          '+' + '-' * 13 + '+']
A(make_case('all-op-classes', from_art(allops), [1] * 10,
            note='^ > v < digits M + - X H all present'))


# ------------------------------------------------- '+'/'-' wall-vs-op traps
A(make_case('swan-dive-clone', from_art(['+--------+', '|@8-+2MX |', '|        |',
                                         '|        |', '+--------+']), [1] * 8,
            note="public 'swan dive' shape: '+' and '-' as INSTRUCTIONS"))
A(make_case('pm-first-row', from_art(['+------+', '|-+-+-@|', '|      |',
                                      '|      |', '+------+']), [1],
            note="a full run of '-'/'+' on the first interior row, hugging the walls"))
A(make_case('pm-false-wall-row', from_art(['+------+', '|@9M   |', '|------|',
                                           '|  ++  |', '|      |', '+------+']),
            [1] * 8, note='an interior row that looks exactly like a wall'))
A(make_case('pm-false-corner-col', from_art(['+------+', '|@+   v|', '|+    -|',
                                             '|+    -|', '|     <|', '+------+']),
            [1] * 14, note="interior columns of '+' and '-' that mimic wall columns"))
A(make_case('pm-under-corner', from_art(['+----+', '|+--+|', '|@  v|', '|+--+|',
                                         '|   <|', '+----+']), [1] * 10,
            note='an entire fake ROOM drawn inside the real room out of +/- '))
A(make_case('pm-arith-adjacent', from_art(['+------+', '|@1M+++|', '|      |',
                                           '|      |', '+------+']), [1] * 6,
            note="'+' instructions running right up to the east wall"))
A(make_case('pm-all-interior', framed(8, 6, lambda x, y: '@' if (x, y) == (1, 1)
                                      else ('+' if (x + y) % 2 else '-')), [1] * 6,
            note="every interior cell is '+' or '-'"))
A(make_case('pm-corner-neighbours', from_art(['+-----+', '|-@---|', '|+   +|',
                                              '|+   +|', '|-----|', '+-----+']),
            [1] * 6, note='+/- ops in every cell that touches a real wall'))


# ------------------------------------------------------------ display edges
A(make_case('man-on-last-pixel', framed(16, 16, lambda x, y: '@' if (x, y) == (14, 14)
                                        else ' '), [1],
            note='man halts on the display corner pixel (15,14)'))
A(make_case('dense16-ops', framed(16, 16, lambda x, y: '@' if (x, y) == (1, 1) else
                                  OPS[(x * 7 + y * 3) % len(OPS)]), [1] * 20,
            note='every interior cell carries an op: max colour variety'))


# ------------------------------------------------------------------ fuzz set
def fuzz(seed, small_k):
    r = random.Random(seed * 7919 + (1 if small_k else 0))
    W = r.randint(4, 16)
    H = r.randint(4, 16)
    pool = OPS + '     ' + ('H' if r.random() < 0.5 else '')
    sx = r.randint(1, W - 2)
    sy = r.randint(1, H - 2)

    def fill(x, y):
        if (x, y) == (sx, sy):
            return '@'
        return r.choice(pool)
    rows = framed(W, H, fill)
    ks = []
    budget = 200
    while budget > 0 and len(ks) < 29:
        k = r.randint(1, 4) if small_k else r.randint(1, min(64, budget))
        k = min(k, budget)
        ks.append(k)
        budget -= k
        if not small_k and r.random() < 0.35:
            break
    return make_case('fuzz%s-%02d' % ('k1' if small_k else 'kb', seed), rows, ks,
                     note='random %dx%d' % (W, H))


for s in range(30):
    A(fuzz(s, True))
for s in range(30):
    A(fuzz(s, False))


# ------------------------------------------- 64-bit A: overflow through X
def doubler(cw, seed_ops, name, note, ks):
    """A ring of 'M','+' pairs (A doubles every lap) entered from a corridor.

    The seed digits sit on the ENTRY corridor so they run exactly once; on the
    ring the only ops are M/+ and the four corner turns, one of which is an 'X'
    that happens to agree with the ring's own turn while sign(A) is unchanged.
    When A wraps past 2**63 the X turns the other way and the man leaves the
    ring, so the HALT POSITION is a direct read-out of 64-bit wrapping.
    """
    x0 = 2 + len(seed_ops)           # the corridor turns south INTO the ring
    x1, y0, y1 = x0 + 5, 3, 9
    W, H = x1 + 2, 12
    g = [[' '] * W for _ in range(H)]
    for x in range(W):
        g[0][x] = g[H - 1][x] = '-'
    for y in range(H):
        g[y][0] = g[y][W - 1] = '|'
    for (x, y) in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        g[y][x] = '+'
    # entry corridor along row 1: @ then the seed, then 'v' down column 4
    g[1][1] = '@'
    for i, ch in enumerate(seed_ops):
        g[1][2 + i] = ch
    g[1][x0] = 'v'
    ring = [(x, y0) for x in range(x0, x1 + 1)] + \
           [(x1, y) for y in range(y0 + 1, y1 + 1)] + \
           [(x, y1) for x in range(x1 - 1, x0 - 1, -1)] + \
           [(x0, y) for y in range(y1 - 1, y0, -1)]
    if not cw:
        ring = [ring[0]] + ring[1:][::-1]
    corners = {(x0, y0): '>' if cw else 'v', (x1, y0): 'v' if cw else '<',
               (x1, y1): '<' if cw else '^', (x0, y1): '^' if cw else '>'}
    if cw:
        corners[(x1, y0)] = 'X'      # east -> south is the CW turn
    else:
        corners[(x0, y1)] = 'X'      # south -> east is the CCW turn
    free = [c for c in ring if c not in corners]
    for i, (x, y) in enumerate(free):
        g[y][x] = 'M' if i % 2 == 0 else '+'
    for (x, y), ch in corners.items():
        g[y][x] = ch
    if not cw:                       # enter the ring heading south at (4,3)
        g[y0][x0] = 'v'
        corners[(x0, y0)] = 'v'
    return make_case(name, [''.join(r) for r in g], ks, note=note)


A(doubler(True, '9M', 'wrap64-positive', 'A doubles from 9 until it wraps NEGATIVE past 2**63; '
          'the X on the ring then turns the wrong way and the man dies on a wall',
          [64, 64, 64, 8]))
A(doubler(False, '9M0-', 'wrap64-negative', 'A doubles from -9 until it wraps POSITIVE past '
          '-2**63; the X then turns the wrong way', [64, 64, 64, 8]))


# ------------------------------------------------ max rounds / delta traffic
A(make_case('max-rounds-30', from_art(ring16), [6] * 29,
            note='29 step rounds (30 total), 174 ticks: maximum frame traffic'))
A(make_case('k-values-8-16-59', from_art(ring16), [8, 16, 59, 8, 16, 59],
            note='k values the rest of the suite never uses'))
A(make_case('max-rounds-k1', from_art(lap), [1] * 29,
            note='29 rounds of k=1 on a forever-lap: one delta per round'))

# man halting exactly on each of the four room CORNER cells
A(make_case('corner-halt-nw', from_art(['+----+', '|@<  |', '|^   |', '|    |',
                                        '+----+']), [1, 1, 1, 1],
            note='never actually reaches the corner: walks west into the west wall'))
A(make_case('corner-halt-se-16', framed(16, 16, lambda x, y: '@' if (x, y) == (14, 14)
                                        else ('v' if (x, y) == (14, 13) else ' ')),
            [1, 1, 1], note='halt at the far display edge of a full-size program'))


# ------------------------------------------------------- OUT OF SPEC probes
oos.append(make_case('oos-k0', blank(6, 6), [0, 0, 1, 0, 1],
                     note='k = 0 rounds (spec says 1 <= k <= 64)'))
oos.append(make_case('oos-post-halt', from_art(['+--+', '|@ |', '|  |', '+--+']),
                     [1, 1, 1, 64, 64], allow_post_halt=True,
                     note='step commands after the halt (spec says they never arrive)'))
oos.append(make_case('oos-3x3', from_art(['+-+', '|@|', '+-+']), [1, 1],
                     note='3x3 room (spec says 4 <= W,H)'))
oos.append(make_case('oos-k64-x8', from_art(lap), [64] * 8,
                     note='512 ticks (spec says at most 200 per case)'))
# Rooms that do not fill the whole program grid.  Every public case has
# room == grid, and the spec only promises "a single room", so this is a
# plausible-but-unseen shape rather than a guaranteed one.
oos.append(make_case('oos-inset-room-tl', from_art(
    ['        ', ' +----+ ', ' |@  v| ', ' |    | ', ' |^  <| ', ' +----+ ',
     '        ', '        ']), [1] * 12,
    note='6x5 room inset by 1 inside an 8x8 program grid'))
oos.append(make_case('oos-inset-room-br', from_art(
    ['          ', '          ', '   +-----+', '   |@   v|',
     '   |     |', '   |^   <|', '   +-----+']), [1] * 12,
    note='room pushed to the bottom-right of the program grid'))


# --------------------------------------------- ZERO-delta consecutive frames
# The champion emits DELTAS ("only two pixels change between frames").  A lap
# whose length divides k puts the man back where he started, so the next frame
# is BYTE-IDENTICAL to the previous one and the delta is EMPTY -- the frame
# still has to be committed.
ring12 = ['+----+', '|>@>v|', '|^  v|', '|^  v|', '|^<<<|', '+----+']
A(make_case('zero-delta-12', from_art(ring12), [12] * 16,
            note='12-cell lap stepped 12 at a time: every frame identical to the last'))
A(make_case('zero-delta-mixed', from_art(ring12), [12, 1, 11, 24, 36, 48, 60, 12, 5],
            note='alternating empty and non-empty deltas'))
A(make_case('zero-delta-16', from_art(ring16), [52] * 3 + [26, 26],
            note='16x16 lap: 52 ticks is exactly one lap, so no pixel changes'))

# ------------------------------------------------------------- big fuzz set
big = []
for s in range(200):
    big.append(fuzz(1000 + s, s % 2 == 0))


def write(path, group):
    json.dump({'publicTestData': [{'name': c['name'], 'rounds': c['rounds']} for c in group],
               'tickCap': 20000000, 'scoring': 'footprint-tick'},
              open(path, 'w'))
    return len(group)


if __name__ == '__main__':
    n1 = write(os.path.join(REPO, 'tests', 'lllm-adv.json'), cases)
    n2 = write(os.path.join(REPO, 'tests', 'lllm-oos.json'), oos)
    n3 = write(os.path.join(REPO, 'tests', 'lllm-fuzz.json'), big)
    print('big fuzz %d cases' % n3)
    meta = {c['name']: c['_meta'] for c in cases + oos + big}
    json.dump(meta, open(os.path.join(REPO, 'scratchpad', 'lllm_adv_meta.json'), 'w'),
              indent=1)
    print('in-spec %d cases, out-of-spec %d cases' % (n1, n2))
    for c in cases + oos:
        m = c['_meta']
        print('  %-20s %2dx%-2d rounds=%2d ticks=%3d halted=%-5s %s'
              % (c['name'], m['W'], m['H'], len(c['rounds']), m['ticks'],
                 m['halted'], m['note']))
