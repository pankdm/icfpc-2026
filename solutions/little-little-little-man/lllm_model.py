#!/usr/bin/env python3
"""Reference model for the LLLM problem (slug: little-little-little-man).

Dependency-free (stdlib only).  This is the *oracle* the .man generator is
checked against: it defines, in ordinary Python, exactly what the littleman
program has to compute.

Language (see tests/little-little-little-man.json "description"):

    ^ > v <   set heading N / E / S / W
    0-9       A = n
    M         B = A
    +         A = A + B
    -         A = A - B
    X         turn CW if A > 0, CCW if A < 0, no turn if A = 0
    H         halt (man stays on the H forever)
    space     no-op

Each tick: execute the cell under the man, THEN advance one cell along the
heading.  If the cell he advances into is a room wall he moves ONTO it and
halts there forever (this differs from littleman, where that is fatal).

Round 1 supplies `W H` then W*H ASCII codes, row-major; commit one frame of the
starting state.  Every later round supplies one `k`; step k ticks (or until
halt) and commit one frame.

Display is 16x16.  Colours:
    wall 4 | "<>^vXH" 3 | "0"-"9" 8 | "M" 12 | "+-" 10 | space 0 | MAN 9
The man is drawn on top of whatever he stands on (instruction or wall).  Cells
outside the W*H program stay black (0).

Run this file directly to validate against every public case in the cached
spec.
"""

import json
import os
import sys

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

DISPLAY_W = 16
DISPLAY_H = 16
DISPLAY_N = DISPLAY_W * DISPLAY_H

WALL = 4
MAN = 9
C_SPACE = 0
C_ARROW = 3      # < > ^ v X H
C_DIGIT = 8      # 0-9
C_M = 12         # M
C_PM = 10        # + -

# headings, index order is CLOCKWISE: N, E, S, W
NORTH, EAST, SOUTH, WEST = 0, 1, 2, 3
DELTA = {NORTH: (0, -1), EAST: (1, 0), SOUTH: (0, 1), WEST: (-1, 0)}
HEADING_OF = {'^': NORTH, '>': EAST, 'v': SOUTH, '<': WEST}

MASK64 = (1 << 64) - 1


def _wrap64(v):
    """Wrap to signed 64-bit, as littleman arithmetic does."""
    v &= MASK64
    return v - (1 << 64) if v >= (1 << 63) else v


# --------------------------------------------------------------------------
# program / grid
# --------------------------------------------------------------------------

class Grid(object):
    """A parsed LLLM program: characters plus the room-wall mask."""

    __slots__ = ('w', 'h', 'cells', 'wall', 'start')

    def __init__(self, w, h, cells, wall, start):
        self.w = w
        self.h = h
        self.cells = cells    # list of row strings, each of length w
        self.wall = wall      # set of (x, y) that are room wall cells
        self.start = start    # (x, y) of the '@'

    def at(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.cells[y][x]
        return None

    def is_wall(self, x, y):
        # Anything off the program grid is treated as a wall too, so a man can
        # never escape.  Well-formed inputs never need this.
        if not (0 <= x < self.w and 0 <= y < self.h):
            return True
        return (x, y) in self.wall

    def __str__(self):
        return '\n'.join(self.cells)


def _find_room(cells, w, h):
    """Locate the single room and return its wall cells.

    A room is a rectangle whose corners are '+', horizontal walls '-' and
    vertical walls '|'.  '+' and '-' are also *instructions*, so we cannot just
    colour every '+'/'-' as wall (public case 7, "swan dive", has "|@8-+2MX |"
    with both inside the room).

    Everything outside the room is spaces, so the FIRST '+' in reading order is
    always the room's top-left corner.  From there we walk right along the top
    wall to the top-right '+', and down the left wall to the bottom-left '+'.
    """
    x0 = y0 = None
    for y in range(h):
        row = cells[y]
        for x in range(w):
            if row[x] == '+':
                x0, y0 = x, y
                break
        if x0 is not None:
            break
    if x0 is None:
        # No corner found: fall back to the perimeter of the whole grid.
        return _perimeter(w, h, 0, 0, w - 1, h - 1)

    x1 = None
    x = x0 + 1
    while x < w:
        c = cells[y0][x]
        if c == '+':
            x1 = x
            break
        if c != '-':
            break
        x += 1

    y1 = None
    y = y0 + 1
    while y < h:
        c = cells[y][x0]
        if c == '+':
            y1 = y
            break
        if c != '|':
            break
        y += 1

    if x1 is None or y1 is None:
        return _perimeter(w, h, 0, 0, w - 1, h - 1)
    return _perimeter(w, h, x0, y0, x1, y1)


def _perimeter(w, h, x0, y0, x1, y1):
    wall = set()
    for x in range(x0, x1 + 1):
        wall.add((x, y0))
        wall.add((x, y1))
    for y in range(y0, y1 + 1):
        wall.add((x0, y))
        wall.add((x1, y))
    return wall


def parse_program(values, W, H):
    """values: W*H ASCII codes (ints or 1-char strings), row-major.

    Returns a Grid.  The '@' is recorded as the start position and the cell
    itself becomes ordinary space (walking back over it does nothing).
    """
    if len(values) != W * H:
        raise ValueError('expected %d values, got %d' % (W * H, len(values)))
    chars = []
    for v in values:
        if isinstance(v, str):
            chars.append(v if len(v) == 1 else chr(int(v)))
        else:
            chars.append(chr(int(v)))

    cells = [''.join(chars[y * W:(y + 1) * W]) for y in range(H)]
    wall = _find_room(cells, W, H)

    start = None
    for y in range(H):
        x = cells[y].find('@')
        if x >= 0:
            start = (x, y)
            cells[y] = cells[y][:x] + ' ' + cells[y][x + 1:]
            break
    if start is None:
        raise ValueError('program has no @')
    return Grid(W, H, cells, wall, start)


# --------------------------------------------------------------------------
# machine state
# --------------------------------------------------------------------------

class State(object):
    """The little man: position, heading, registers, halted flag."""

    __slots__ = ('grid', 'x', 'y', 'dir', 'a', 'b', 'halted')

    def __init__(self, grid, x, y, d=EAST, a=0, b=0, halted=False):
        self.grid = grid
        self.x = x
        self.y = y
        self.dir = d
        self.a = a
        self.b = b
        self.halted = halted

    def copy(self):
        return State(self.grid, self.x, self.y, self.dir,
                     self.a, self.b, self.halted)

    @property
    def man(self):
        return (self.x, self.y)

    def __repr__(self):
        return ('State(pos=(%d,%d) dir=%s A=%d B=%d halted=%s)'
                % (self.x, self.y, 'NESW'[self.dir], self.a, self.b,
                   self.halted))


def initial_state(grid):
    """The man spawns at '@' facing EAST with A = B = 0."""
    return State(grid, grid.start[0], grid.start[1], EAST, 0, 0, False)


def step(state):
    """Advance one LLLM tick.  Mutates and returns `state`.

    Execute the cell under the man, then move one cell along the heading.  If
    the destination is a wall, the man moves onto that wall cell and halts.
    """
    if state.halted:
        return state

    g = state.grid
    c = g.at(state.x, state.y)

    if c == 'H':
        state.halted = True
        return state
    elif c == 'M':
        state.b = state.a
    elif c == '+':
        state.a = _wrap64(state.a + state.b)
    elif c == '-':
        state.a = _wrap64(state.a - state.b)
    elif c == 'X':
        if state.a > 0:
            state.dir = (state.dir + 1) & 3          # clockwise
        elif state.a < 0:
            state.dir = (state.dir - 1) & 3          # counter-clockwise
    elif c in HEADING_OF:
        state.dir = HEADING_OF[c]
    elif c is not None and '0' <= c <= '9':
        state.a = ord(c) - 48
    # space (and the vacated '@') are no-ops.

    dx, dy = DELTA[state.dir]
    nx, ny = state.x + dx, state.y + dy
    state.x, state.y = nx, ny
    if g.is_wall(nx, ny):
        state.halted = True
    return state


def run_ticks(state, k):
    """Step up to k ticks, stopping early on halt."""
    for _ in range(k):
        if state.halted:
            break
        step(state)
    return state


# --------------------------------------------------------------------------
# display
# --------------------------------------------------------------------------

def colour_of(ch):
    if ch == ' ' or ch is None:
        return C_SPACE
    if ch in '<>^vXH':
        return C_ARROW
    if '0' <= ch <= '9':
        return C_DIGIT
    if ch == 'M':
        return C_M
    if ch in '+-':
        return C_PM
    return C_SPACE


def frame(grid, man):
    """256 colour values, row-major, in the display's expected order.

    `man` is an (x, y) tuple (or None).  The man is drawn on top of whatever
    he stands on -- walls and instructions included.
    """
    out = [C_SPACE] * DISPLAY_N
    for y in range(min(grid.h, DISPLAY_H)):
        row = grid.cells[y]
        base = y * DISPLAY_W
        for x in range(min(grid.w, DISPLAY_W)):
            if (x, y) in grid.wall:
                out[base + x] = WALL
            else:
                out[base + x] = colour_of(row[x])
    if man is not None:
        mx, my = man
        if 0 <= mx < DISPLAY_W and 0 <= my < DISPLAY_H:
            out[my * DISPLAY_W + mx] = MAN
    return out


def frame_lines(colours):
    """Format 256 colour values as the 16 hex strings the grader compares."""
    return [''.join('%x' % c for c in colours[y * DISPLAY_W:(y + 1) * DISPLAY_W])
            for y in range(DISPLAY_H)]


# --------------------------------------------------------------------------
# whole-case driver
# --------------------------------------------------------------------------

def run_case(rounds):
    """rounds: list of per-round input lists of ints (or numeric strings).

    Round 0 is [W, H, *ascii]; every later round is [k].
    Returns one frame (list of 256 colour values) per round.
    """
    rounds = [[int(v) for v in r] for r in rounds]
    first = rounds[0]
    W, H = first[0], first[1]
    grid = parse_program(first[2:], W, H)
    st = initial_state(grid)

    frames = [frame(grid, st.man)]
    for r in rounds[1:]:
        run_ticks(st, r[0])
        frames.append(frame(grid, st.man))
    return frames


def run_case_lines(rounds):
    return [frame_lines(f) for f in run_case(rounds)]


# --------------------------------------------------------------------------
# validation against the cached spec
# --------------------------------------------------------------------------

def _spec_path():
    here = os.path.abspath(__file__)
    for _ in range(6):
        here = os.path.dirname(here)
        p = os.path.join(here, 'tests', 'little-little-little-man.json')
        if os.path.exists(p):
            return p
    raise IOError('tests/little-little-little-man.json not found')


def validate(path=None, verbose=True):
    """Check every public round.  Returns (matched, total, failures)."""
    spec = json.load(open(path or _spec_path()))
    total = matched = 0
    failures = []
    for ci, case in enumerate(spec['publicTestData']):
        rounds = case['rounds']
        got = run_case_lines([r['in'] for r in rounds])
        for ri, r in enumerate(rounds):
            exp = r['frames']
            total += 1
            mine = [got[ri]]
            if mine == exp:
                matched += 1
            else:
                failures.append((ci, case.get('name'), ri, exp, mine))
        if verbose:
            bad = sum(1 for f in failures if f[0] == ci)
            print('case %d %-22r rounds=%2d  %s'
                  % (ci, case.get('name'), len(rounds),
                     'OK' if bad == 0 else 'FAIL x%d' % bad))
    if verbose:
        print('\n%d/%d rounds matched' % (matched, total))
        for ci, name, ri, exp, mine in failures[:3]:
            print('\n-- case %d (%s) round %d' % (ci, name, ri))
            e = exp[0] if exp and isinstance(exp[0], list) else exp
            m = mine[0]
            for a, b in zip(e, m):
                print('   exp %s   got %s %s' % (a, b, '' if a == b else '<<'))
    return matched, total, failures


if __name__ == '__main__':
    m, t, f = validate(sys.argv[1] if len(sys.argv) > 1 else None)
    sys.exit(0 if m == t else 1)
