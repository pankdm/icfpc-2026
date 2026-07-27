#!/usr/bin/env python3
"""Unit test: can search.route() reproduce the four pipes of the working 14x14 rig?"""
import os
import sys

os.environ.setdefault('SORTBOX', '14')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import search as S

rooms = {'main': (0, 0, 9, 7), 'inp': (11, 0, 13, 2),
         'outp': (8, 10, 10, 12), 'relay': (0, 10, 4, 13)}
plan = S.Plan(rooms)
print('BOX', S.BOX, 'free', len(plan.free))
print('main srcs', sorted(c for c, d in plan.srcs('main')))
print('main dsts', sorted(c for c, d in plan.dsts('main')))
print('relay srcs', sorted(c for c, d in plan.srcs('relay')))
print('relay dsts', sorted(c for c, d in plan.dsts('relay')))
print('inp srcs', sorted(c for c, d in plan.srcs('inp')))
print('outp dsts', sorted(c for c, d in plan.dsts('outp')))

tests = [
    ('main->relay', (2, 8), (0, 1), (2, 9), (0, 1), 2, 8),
    ('main->outp', (9, 8), (0, 1), (9, 9), (0, 1), 2, 8),
    ('inp->main', (12, 3), (0, 1), (10, 4), (-1, 0), 2, 20),
    ('relay->main', (5, 13), (1, 0), (10, 6), (-1, 0), 2, 30),
]
for name, s, sd, e, ed, lo, hi in tests:
    r = S.route(plan, s, sd, e, ed, set(), lo, hi, want=3, budget=200000)
    print(name, 'paths', len(r), [len(p[0]) for p in r])
