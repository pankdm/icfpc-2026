#!/usr/bin/env python3
"""Static literal lint: apply the oracle's literal rule to .man files and report violations.

THE RULE (pinned against the oracle by the probes next to this file):
  literals are parsed PER ROOM, over the room's INTERIOR only. Within one interior row (and
  one interior column) backticks pair consecutively (0,1),(2,3),...; the span between a pair
  must be digits or spaces, else load error. A backtick with no partner on either axis is an
  `unmatched backtick` load error.

The disproved hypothesis worth remembering: pairing is NOT a global row/column scan. That
version pairs two literals that sit in DIFFERENT rooms on the same row, across the wall
between them, and rejects 33 of our own files (all subset-sum/parallel*, sort-numbers/
merge-mergercell-v1). It is the bug this probe set was written to find.

usage: python3 check_strict.py 'solutions/*/*.man'
"""
import sys, glob


def grid(path):
    with open(path) as f:
        lines = f.read().split('\n')
    while lines and lines[-1] == '':
        lines.pop()
    w = max((len(l) for l in lines), default=0)
    return [l.ljust(w) for l in lines], w


def rooms_of(g, w, h):
    """Ordinary rooms: '+' corners with '-' top/bottom and '|' sides. Good enough for a lint."""
    out = []
    for top in range(h):
        for left in range(w):
            if g[top][left] != '+':
                continue
            right = next((x for x in range(left + 1, w)
                          if g[top][x] == '+' or g[top][x] != '-'), None)
            if right is None or g[top][right] != '+':
                continue
            bottom = next((y for y in range(top + 1, h)
                           if g[y][left] == '+' or g[y][left] != '|'), None)
            if bottom is None or g[bottom][left] != '+':
                continue
            if g[bottom][right] != '+':
                continue
            out.append((left, top, right, bottom))
    return out


def check(path):
    g, w = grid(path)
    h = len(g)
    bad, paired = [], set()

    def scan(get, span, positions):
        ticks = [i for i in positions if get(i) == '`']
        for k in range(0, len(ticks) - 1, 2):
            a, b = ticks[k], ticks[k + 1]
            for p in range(a + 1, b):
                c = get(p)
                if c != ' ' and not c.isdigit():
                    bad.append(f"non-digit {c!r} between ticks at {span(a)}..{span(b)}")
                    break
            paired.add(span(a))
            paired.add(span(b))

    for (left, top, right, bottom) in rooms_of(g, w, h):
        for y in range(top + 1, bottom):
            scan(lambda x, y=y: g[y][x], lambda x, y=y: (x, y), range(left + 1, right))
        for x in range(left + 1, right):
            scan(lambda y, x=x: g[y][x], lambda y, x=x: (x, y), range(top + 1, bottom))

    for y in range(h):
        for x in range(w):
            if g[y][x] == '`' and (x, y) not in paired:
                bad.append(f"unmatched backtick at ({x},{y})")
    return bad


if __name__ == '__main__':
    pats = sys.argv[1:] or ['solutions/*/*.man']
    files = []
    for p in pats:
        files += glob.glob(p)
    nbad = 0
    for f in sorted(files):
        b = check(f)
        if b:
            nbad += 1
            print(f"{f}: {len(b)} issue(s)")
            for m in b[:5]:
                print("   ", m)
    print(f"checked {len(files)} files, {nbad} with issues")
