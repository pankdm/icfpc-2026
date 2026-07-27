#!/usr/bin/env python3
"""Probe rig: swaps ONLY p2's point list in rewind_incell_build.py and asks the
oracle whether the program loads / passes.  Two rules were pinned down with it.

Geometry it assumes: MEM cols 0-18 rows 0-12 (east wall col 18, so col 19 is the
flush column), HOP cols 15-22 rows 16-22, CONTROL cols 3-12 rows 16-22.  p2
flows HOP -> MEM.

*** RULE 1 -- FLUSH IS ABOUT THE *DESTINATION* ROOM, AND ONE CELL IS ENOUGH. ***
    base (col 19 touched only at rows 13-14)          7/7
    ONE cell of col 19 beside MEM's east wall         loaderror "pipe loops back
                                                      to the room it started from"
    13 cells of col 19 beside MEM's east wall         same loaderror
    p2 hugging HOP's west wall (col 14, 7 cells)      fine -- the shipped build
    p2 hugging HOP's east wall (col 23, 7 cells)      fine -- the shipped build
    p2 hugging CONTROL's east wall (col 13)           fine -- the shipped build
    a run along HOP's TOP wall (row 15, cols 16-21)   same loaderror
So it is NOT "no pipe may hug a wall".  A pipe may hug rooms it does not attach
to, and may hug the SOURCE room's side walls, but NO intermediate cell may be
adjacent to the room the pipe terminates at -- consistent with the parser
walking from the MEM end and rejecting any later cell adjacent to MEM.  The
error text names "the room it started from", i.e. the end it walked from.

    p2 MAY terminate on MEM's EAST wall: [(21,15),(21,14),(20,14),(20,6),(19,6)]
    loads (0/7 only because that p2 is 5 cells).  The final segment must point
    INTO the wall -- approaching (19,6) from the north instead of the east gives
    "pipe ends without reaching another room", and a flush RUN up col 19 into
    the attachment gives the same, so the run is not absorbed into the endpoint.

*** RULE 2 -- THE BELT FLOOR IS EXACTLY 99, BISECTED BOTH PARITIES. ***
A pipe's endpoints fix its length PARITY, so this took two endpoint choices:
    HOP attach col 21 (odd lengths):  103 7/7   101 7/7   99 7/7   97 2/7
                                       95 6/7    93 5/7   91 0/7
    HOP attach col 20 (even lengths): 102 7/7   100 7/7   98 2/7   96 5/7
99 passes, 98 fails.  Note 95 and 93 pass 6/7 and 5/7 -- a short belt degrades
NON-MONOTONICALLY, so never conclude "long enough" from one sample.

usage: python3 flushprobe.py
"""
import os, re, subprocess, sys

W = '/Users/visenbaev/icfpc26/.claude/worktrees/agent-aee9675e7ff977bae'
SRC = os.path.join(W, 'solutions', 'memory', 'rewind_incell_build.py')
OUT = os.path.join(W, 'solutions', 'memory', '_probe')

# v14/incell baseline tail, shared by most variants (isthmus serpentine + the
# westward run on row 14 into MEM's BOTTOM wall at X_P2=9).
TAIL = """(14, 23),
          (13, 23), (13, 22), (14, 22), (14, 21), (13, 21), (13, 20),
          (14, 20), (14, 19), (13, 19), (13, 18), (14, 18), (14, 17),
          (13, 17), (13, 16), (14, 16), (14, 15), (13, 15),
          (13, 14), (X_P2, 14), (X_P2, PIPE_ROW)]"""

VARIANTS = {
    'base': """[(21, 15), (21, 14), (20, 14), (19, 14), (19, 13), (20, 13),
          (20, 0), (21, 0), (21, 13),
          (22, 13), (22, 0), (23, 0), (23, 23),
          """ + TAIL,
}


def build(name, p2src):
    s = open(SRC).read()
    i = s.index('    p2 = [')
    j = s.index('    for pts in (out, cmd, ipipe, p1, p2):')
    s = s[:i] + '    p2 = ' + p2src + '\n' + s[j:]
    man = OUT + '-' + name + '.man'
    s = s.replace("'rewind-incell.man'", repr(os.path.basename(man)))
    py = OUT + '-' + name + '.py'
    open(py, 'w').write(s)
    r = subprocess.run([sys.executable, py], capture_output=True, text=True)
    return man, r.stderr.strip().splitlines()[-1] if r.returncode else ''


def grade(man):
    r = subprocess.run(['node', os.path.join(W, 'tools', 'grade.js'), 'memory', man],
                       capture_output=True, text=True)
    txt = r.stdout
    m = re.search(r'loaderror: ([^\n]+)', txt)
    if m:
        return 'LOAD ERROR: ' + m.group(1)[:70]
    m = re.search(r'(\d)/7 public', txt)
    return ('%s/7' % m.group(1)) if m else txt.strip()[:80]


for name, p2src in VARIANTS.items():
    man, err = build(name, p2src)
    print('%-22s %s' % (name, err if err else grade(man)))
