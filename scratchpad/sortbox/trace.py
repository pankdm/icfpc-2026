#!/usr/bin/env python3
"""Trace a sort-numbers .man on a hand-given round list.

usage: trace.py <file.man> "3 1 2" [more rounds...]   -> prints q events + ring fill
       trace.py <file.man> --cells "3 1 2" ...        -> per-cell visit counts (room 0)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from interpreter.parser import load_program
from interpreter.machine import LittlemanMachine

path = sys.argv[1]
args = sys.argv[2:]
mode = "q"
if args and args[0] == "--cells":
    mode = "cells"; args = args[1:]

rounds_in = []
rounds_out = []
for a in args:
    vals = [int(t) for t in a.split()]
    rounds_in.append([len(vals)] + vals)
    rounds_out.append(sorted(vals))

prog = load_program(path)
grid = prog.grid if hasattr(prog, "grid") else None
m = LittlemanMachine(prog, rounds_in, rounds_out, tick_limit=200000)

visits = {}
events = []
orig_tick = m._tick


def fill(ps):
    return sum(1 for v in ps.values if v is not None)


def tick():
    # record what each man is about to execute
    pre = [(man.position, man.backpack, man.main, man.off) for man in m.men if not man.stopped]
    cells = [prog.cell(man.position) for man in m.men if not man.stopped]
    orig_tick()
    for (pos, bp, a, b), ch in zip(pre, cells):
        if mode == "cells":
            visits[pos] = visits.get(pos, 0) + 1
        if ch == "q":
            events.append((m.ticks, pos, [fill(p) for p in m.pipes]))


m._tick = tick
res = m.run()
print("status", res.status, "ticks", res.ticks, "err", res.error)
print("out", res.output)
if mode == "cells":
    for pos, n in sorted(visits.items(), key=lambda kv: -kv[1]):
        print(f"  {pos} {prog.cell(pos)!r} {n}")
else:
    for t, pos, fills in events:
        print(f"  t={t} q@{pos} pipefill={fills}")
