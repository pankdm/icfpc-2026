#!/usr/bin/env python3
"""mm2 probes: serpentine pipe legality, self-loop pipe legality, opt5 baselines."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')


def run(prog_text, inp, exp, steps=None):
    path = '/tmp/mm2probe.man'
    open(path, 'w').write(prog_text + '\n')
    cmd = [LM, '--grade', path, f'--input={inp}', f'--expected={exp}', '--cap=200000']
    out = subprocess.run(cmd, capture_output=True, text=True)
    return out.stdout.strip() + out.stderr.strip()[:300]


def probe_serpentine():
    """A pipe folded with NO gap between adjacent rows: is it parsed as one pipe?"""
    p = Program()
    # room A (source) at 0,0 5x3 ; room B (dest) far right
    p.input_room(0, 0)
    p.room(0, 5, 6, 4)
    p.text(1, 6, "@rsv")
    p.text(1, 7, "  <")
    p.output_room(20, 0)
    p.pipe([(1, 3), (1, 4)])              # I -> room
    # serpentine from room top (col 3) up then fold
    pts = [(3, 4), (3, 3)]
    # build a serpentine in rows 3..-? use area to the right, rows 0..? Let's serpentine
    # in the band y=12..17 below the room instead.
    p2 = Program()
    p2.input_room(0, 0)
    p2.room(0, 5, 6, 4)
    p2.text(1, 6, "@rsv")
    p2.text(1, 7, "  <")
    p2.output_room(0, 25)
    p2.pipe([(1, 3), (1, 4)])
    # serpentine: leave room bottom at (3,9) go down to row 11, then snake cols 3..14
    way = [(3, 9), (3, 11), (14, 11), (14, 12), (3, 12), (3, 13), (14, 13),
           (14, 14), (3, 14), (3, 15), (1, 15), (1, 24)]
    p2.pipe(way)
    return p2


def probe_selfloop():
    """Pipe whose source and destination are the SAME room."""
    p = Program()
    p.input_room(0, 0)
    p.output_room(8, 0)
    p.room(0, 5, 12, 5)
    # man: read from input, send to self loop, read back from self loop, send to O
    p.text(1, 6, "@rsv")
    p.text(1, 7, "   ")
    p.text(1, 8, ">rs")
    p.pipe([(1, 3), (1, 4)])          # I -> room top col1
    p.pipe([(9, 4), (9, 3)])          # room -> O  (O is at cols 8..10 rows 0..2)
    # self loop: out of room top col 5, around, back into room top col 6
    p.pipe([(5, 4), (5, 2), (6, 2), (6, 4)], end_direction='S')
    return p


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if which in ('all', 'serp'):
        p = probe_serpentine()
        print(p.render())
        print('SERP:', run(p.render(), '7', '7'))
    if which in ('all', 'self'):
        p = probe_selfloop()
        print(p.render())
        print('SELF:', run(p.render(), '7', '7'))
