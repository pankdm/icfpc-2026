#!/usr/bin/env python3
"""Dependency-free reference model for the ICFPC-2026 `snake` problem.

Ground truth for the littleman implementation: round parsing, the tick rule,
and frame rendering.  Run this file to validate it against every public case in
tests/snake.json.

    python3 solutions/snake/snake_model.py            # validate public cases
    python3 solutions/snake/snake_model.py --trace 1  # dump case 1 frame by frame

Semantics (from the problem statement, confirmed against publicTestData):

* Grid is 16x16, top-left is 0,0, x grows right, y grows down.
* Round 1 is `sx sy`: the snake is the single cell (sx,sy), moving RIGHT.
  Commit a frame.
* `1 fx fy`  -- a fruit spawns at (fx,fy).  The game does NOT tick.  Commit a
  frame.  At most one fruit exists at a time and it always lands on an empty
  cell.
* `2|3|4|5`  -- direction := up|right|down|left, effective from the next tick.
  The game does NOT tick.  Do NOT commit a frame.
* `0`        -- advance one tick.  Commit a frame.

Tick rule:

    nh = head + dir
    if nh is off the grid                 -> LOSE (snake does not move)
    elif nh == fruit                      -> GROW: push head, tail stays put,
                                             fruit disappears
    else                                  -> tail is popped FIRST, then
                                             if nh is still occupied -> LOSE
                                             (snake does not move -- the popped
                                             tail is restored for drawing)
                                             else push head

Rendering: one row per grid line, one hex digit per cell.
    snake, game ongoing -> 'a' (colour 10, green)
    snake, game over    -> '9' (colour  9, red)
    fruit               -> '9' (colour  9, red)
    everything else     -> '0' (colour  0, black)
"""

import json
import os
import sys
from collections import deque

N = 16

# direction code -> (dx, dy).  3 == right is the starting direction.
DIRS = {
    2: (0, -1),   # up
    3: (1, 0),    # right
    4: (0, 1),    # down
    5: (-1, 0),   # left
}

GREEN = 'a'
RED = '9'
BLACK = '0'


class Snake:
    """One test case worth of game state."""

    def __init__(self, sx, sy):
        # body[0] is the tail, body[-1] is the head
        self.body = deque([(sx, sy)])
        self.occ = {(sx, sy)}
        self.dir = 3               # right
        self.fruit = None          # (fx, fy) or None
        self.over = False

    # -- rounds ---------------------------------------------------------
    def turn(self, code):
        """Direction change (2/3/4/5).  No tick, no frame."""
        self.dir = code

    def spawn(self, fx, fy):
        """Fruit spawn.  No tick; a frame is committed by the caller."""
        self.fruit = (fx, fy)

    def tick(self):
        """Advance one tick.  A frame is committed by the caller either way."""
        if self.over:
            return
        hx, hy = self.body[-1]
        dx, dy = DIRS[self.dir]
        nx, ny = hx + dx, hy + dy

        if not (0 <= nx < N and 0 <= ny < N):
            self.over = True                       # ran off the board
            return

        if self.fruit is not None and (nx, ny) == self.fruit:
            self.fruit = None                      # grow: tail stays put
            self.body.append((nx, ny))
            self.occ.add((nx, ny))
            return

        tail = self.body.popleft()                 # tail moves BEFORE the head
        self.occ.discard(tail)
        if (nx, ny) in self.occ:                   # still occupied -> lose
            self.body.appendleft(tail)             # snake does not move
            self.occ.add(tail)
            self.over = True
            return
        self.body.append((nx, ny))
        self.occ.add((nx, ny))

    # -- rendering ------------------------------------------------------
    def frame(self):
        grid = [[BLACK] * N for _ in range(N)]
        colour = RED if self.over else GREEN
        for (x, y) in self.body:
            grid[y][x] = colour
        if self.fruit is not None:
            fx, fy = self.fruit
            grid[fy][fx] = RED
        return [''.join(row) for row in grid]


def run_case(round_inputs):
    """round_inputs: list of lists of int-ish tokens, one per round.

    Returns the list of committed frames (each a list of 16 strings), in order.
    Rounds after a loss are ignored -- the test case ends there.
    """
    frames = []
    game = None
    for toks in round_inputs:
        vals = [int(t) for t in toks]
        if game is None:                     # round 1: sx sy
            game = Snake(vals[0], vals[1])
            frames.append(game.frame())
            continue
        if game.over:
            break
        op = vals[0]
        if op == 0:
            game.tick()
            frames.append(game.frame())
        elif op == 1:
            game.spawn(vals[1], vals[2])
            frames.append(game.frame())
        else:
            game.turn(op)                    # no frame
    return frames


# ----------------------------------------------------------------------
# validation against tests/snake.json


def _spec_path():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, 'tests', 'snake.json')


def validate(trace_case=None):
    with open(_spec_path()) as fh:
        spec = json.load(fh)

    total = matched = 0
    case_report = []
    for ci, case in enumerate(spec['publicTestData']):
        rounds = case['rounds']
        expected = [f for r in rounds for f in r['frames']]
        got = run_case([r['in'] for r in rounds])

        n_exp = len(expected)
        n_got = len(got)
        ok = 0
        for i in range(min(n_exp, n_got)):
            if got[i] == expected[i]:
                ok += 1
            elif trace_case is not None and ci == trace_case:
                print('case %d frame %d MISMATCH' % (ci, i))
                for a, b in zip(got[i], expected[i]):
                    print('   got %s   exp %s  %s' % (a, b, '' if a == b else '<--'))
        total += n_exp
        matched += ok
        case_report.append((case['name'], n_exp, n_got, ok))

    for name, n_exp, n_got, ok in case_report:
        flag = 'OK ' if (ok == n_exp == n_got) else 'BAD'
        print('%s %-24s frames expected %3d  produced %3d  matched %3d'
              % (flag, name, n_exp, n_got, ok))
    print('TOTAL: %d/%d frames matched across %d public cases'
          % (matched, total, len(case_report)))
    return matched, total


def selftest():
    """Generality checks the public cases do not all exercise."""
    # tail-follow is legal: a 4-cell snake turns into the cell its tail vacates
    g = Snake(5, 5)
    g.fruit = (6, 5); g.tick()
    g.fruit = (7, 5); g.tick()
    g.dir = 4; g.fruit = (7, 6); g.tick()
    assert list(g.body) == [(5, 5), (6, 5), (7, 5), (7, 6)] and not g.over
    g.dir = 5; g.tick()
    g.dir = 2; g.tick()
    assert list(g.body) == [(7, 5), (7, 6), (6, 6), (6, 5)] and not g.over

    # self-collision: game over, body drawn in its PRE-tick position, in red
    g = Snake(2, 2)
    for d, f in [(3, (3, 2)), (3, (4, 2)), (4, (4, 3)), (5, (3, 3))]:
        g.dir = d; g.fruit = f; g.tick()
    before = list(g.body)
    g.dir = 2; g.tick()
    assert g.over and list(g.body) == before and g.frame()[2][3] == RED

    # walking off any of the four edges loses, snake does not move
    for sx, sy, d in [(15, 5, 3), (0, 5, 5), (5, 0, 2), (5, 15, 4)]:
        g = Snake(sx, sy); g.dir = d; g.tick()
        assert g.over and list(g.body) == [(sx, sy)]

    # a 2-cell snake following its own tail survives
    g = Snake(8, 8); g.fruit = (9, 8); g.tick(); g.dir = 4; g.tick()
    assert not g.over and list(g.body) == [(9, 8), (9, 9)]

    # a case with only the starting round commits exactly one frame
    assert len(run_case([['3', '4']])) == 1
    print('selftest: ok')


if __name__ == '__main__':
    tc = None
    if '--trace' in sys.argv:
        tc = int(sys.argv[sys.argv.index('--trace') + 1])
    selftest()
    m, t = validate(tc)
    sys.exit(0 if m == t else 1)
