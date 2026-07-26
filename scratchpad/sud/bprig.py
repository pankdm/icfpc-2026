#!/usr/bin/env python3
"""Standalone rig for the backpack timer: one man, no strips, emit 1 per lap."""
import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
sys.path.insert(0, "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/solutions/sudoku-validity")
from littleman import Program
import bptimer

n = int(sys.argv[1]) if len(sys.argv) > 1 else 13
p = Program()
p.room(0, 0, 12, 14)                 # interior x1..10, y1..12
p.text(1, 1, "@v")                   # walk east onto 'v', drop to the entry row
p.put(2, 2, ">")                     # ... then east into the timer entry
bptimer.place(p, 4, 2, n)            # block cols 3..7, rows 2..10
p.output_room(14, 10)
p.pipe([(12, 11), (13, 11)])
out = "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/scratchpad/sud/bprig.man"
p.save(out)
print(out, p.footprint(), "expected lap", bptimer.lap(n))
print(open(out).read())
