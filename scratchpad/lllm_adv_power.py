#!/usr/bin/env python3
"""How much POWER does tests/lllm-{adv,fuzz}.json actually have?

A suite that everything passes is worthless unless it can also FAIL something.
This injects the classic LLLM implementation bugs into a copy of the reference
simulator and reports, per bug, how many suite cases notice -- and, for
comparison, how many of the 10 PUBLIC cases notice.  A bug that only the
adversarial suite catches is exactly the kind that would score 0 privately.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'little-little-little-man'))
import lllm_model as MOD  # noqa: E402

CW = [MOD.NORTH, MOD.EAST, MOD.SOUTH, MOD.WEST]


def sim(rounds, bug):
    """Run a case the way a buggy implementation would.  Returns frame lines."""
    rounds = [[int(v) for v in r] for r in rounds]
    W, H = rounds[0][0], rounds[0][1]
    grid = MOD.parse_program(rounds[0][2:], W, H)
    st = MOD.initial_state(grid)
    if bug == 'init-north':
        st.dir = MOD.NORTH

    def colour(x, y):
        ch = grid.cells[y][x]
        if bug == 'pm-as-wall' and ch in '+-':
            return MOD.WALL
        if bug == 'colour-H-as-M' and ch == 'H':
            return MOD.C_M
        if bug == 'colour-digit-as-M' and '0' <= ch <= '9':
            return MOD.C_M
        if (x, y) in grid.wall:
            return MOD.WALL
        return MOD.colour_of(ch)

    def frame():
        out = [MOD.WALL if bug == 'pad-outside-wall' else MOD.C_SPACE] * 256
        for y in range(min(H, 16)):
            for x in range(min(W, 16)):
                out[y * 16 + x] = colour(x, y)
        mx, my = st.x, st.y
        if 0 <= mx < 16 and 0 <= my < 16:
            on_wall = (mx, my) in grid.wall
            on_op = grid.cells[my][mx] != ' '
            if bug == 'no-man-on-wall' and on_wall:
                pass
            elif bug == 'man-under-op' and on_op and not on_wall:
                pass
            else:
                out[my * 16 + mx] = MOD.MAN
        return MOD.frame_lines(out)

    def step():
        if st.halted:
            return
        c = grid.at(st.x, st.y)
        if bug == 'exec-after-move':          # move first, then execute
            dx, dy = MOD.DELTA[st.dir]
            st.x, st.y = st.x + dx, st.y + dy
            if grid.is_wall(st.x, st.y):
                st.halted = True
                return
            c = grid.at(st.x, st.y)
        if c == 'H':
            st.halted = True
            if bug == 'H-not-sticky':
                dx, dy = MOD.DELTA[st.dir]
                st.x, st.y = st.x + dx, st.y + dy
            return
        elif c == 'M':
            if bug == 'M-swaps':
                st.a, st.b = st.b, st.a
            else:
                st.b = st.a
        elif c == '+':
            st.a = (st.a - st.b) if bug == 'pm-swap' else (st.a + st.b)
        elif c == '-':
            st.a = (st.a + st.b) if bug == 'pm-swap' else (st.a - st.b)
        elif c == 'X':
            if bug == 'X-uses-B':
                st.dir = (st.dir + (1 if st.b > 0 else 3 if st.b < 0 else 0)) & 3
            elif st.a > 0:
                st.dir = (st.dir + (3 if bug == 'X-inverted' else 1)) & 3
            elif st.a < 0:
                st.dir = (st.dir + (1 if bug == 'X-inverted' else 3)) & 3
        elif c in MOD.HEADING_OF:
            st.dir = MOD.HEADING_OF[c]
        elif c is not None and '0' <= c <= '9':
            st.a = (st.a + ord(c) - 48) if bug == 'digit-accumulates' else ord(c) - 48
        if bug == 'wrap32':
            st.a &= 0xFFFFFFFF
            if st.a >= 1 << 31:
                st.a -= 1 << 32
        elif bug != 'no-wrap':
            st.a = MOD._wrap64(st.a)
        if bug == 'exec-after-move':
            return
        dx, dy = MOD.DELTA[st.dir]
        nx, ny = st.x + dx, st.y + dy
        if grid.is_wall(nx, ny):
            st.halted = True
            if bug == 'halt-before-wall':     # stop on the last interior cell
                return
        st.x, st.y = nx, ny

    frames = [frame()]
    for r in rounds[1:]:
        k = r[0]
        if bug == 'k-off-by-one':
            k = max(0, k - 1)
        for _ in range(k):
            if st.halted:
                break
            step()
        frames.append(frame())
    return frames


BUGS = ['X-inverted', 'halt-before-wall', 'pm-as-wall', 'man-under-op',
        'no-man-on-wall', 'exec-after-move', 'H-not-sticky', 'wrap32',
        'no-wrap', 'M-swaps', 'init-north', 'k-off-by-one', 'pm-swap',
        'X-uses-B', 'digit-accumulates', 'colour-H-as-M', 'colour-digit-as-M',
        'pad-outside-wall']


def load(slug):
    return json.load(open(os.path.join(REPO, 'tests', slug + '.json')))['publicTestData']


def detect(cases, bug):
    n = 0
    for tc in cases:
        rounds = [r['in'] for r in tc['rounds']]
        want = [r['frames'][0] for r in tc['rounds']]
        try:
            got = sim(rounds, bug)
        except Exception:
            n += 1
            continue
        if got != want:
            n += 1
    return n


if __name__ == '__main__':
    pub = load('little-little-little-man')
    adv = load('lllm-adv')
    fuzz = load('lllm-fuzz')
    # sanity: with no bug injected the simulator must reproduce every frame
    for name, cs in (('public', pub), ('adv', adv), ('fuzz', fuzz)):
        assert detect(cs, 'none') == 0, name
    print('%-18s %8s %8s %8s' % ('injected bug', 'public', 'adv', 'fuzz'))
    print('%-18s %8d %8d %8d' % ('(cases)', len(pub), len(adv), len(fuzz)))
    for b in BUGS:
        print('%-18s %8d %8d %8d' % (b, detect(pub, b), detect(adv, b), detect(fuzz, b)))
