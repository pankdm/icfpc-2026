#!/usr/bin/env python3
"""Generate literal-semantics probes.

Frame: output room on top, main room below. The man starts at @ facing east,
hits 'v' in column CX, then walks straight DOWN column CX through the probe
rows, then 's' (send A) and 'H'.

build(name, rows, cx=3): rows is a list of strings = the interior content of
the main room, already positioned so column cx holds what the man walks over.
The 's'/'H' rows are appended automatically.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CX = 3


def build(name, rows, width=None, cx=CX):
    body = ['@'.ljust(cx) + 'v'] + list(rows) + [' ' * cx + 's', ' ' * cx + 'H']
    w = max(len(r) for r in body)
    if width:
        w = max(w, width)
    body = [r.ljust(w) for r in body]
    lines = ['+-+', '|O|', '+-+', ' ^', ' ^', '+' + '-' * w + '+']
    lines += ['|' + r + '|' for r in body]
    lines += ['+' + '-' * w + '+']
    path = os.path.join(HERE, name + '.man')
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    return path


def col(chars, cx=CX, pad=''):
    """one probe row per char, char placed in column cx (0-based inside room)"""
    return [' ' * cx + c + pad for c in chars]
