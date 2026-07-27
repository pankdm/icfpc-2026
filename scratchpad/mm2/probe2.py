#!/usr/bin/env python3
"""Serpentine (gapless folded) pipe: does it load AND transport in order?"""
import os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')


def run(text, inp, exp, cap=200000):
    open('/tmp/mm2p2.man', 'w').write(text + '\n')
    o = subprocess.run([LM, '--grade', '/tmp/mm2p2.man', f'--input={inp}',
                        f'--expected={exp}', f'--cap={cap}'], capture_output=True, text=True)
    return (o.stdout.strip() or o.stderr.strip()[:300])


def serp_pts(x0, y0, width, rows):
    """Gapless boustrophedon waypoints, starting at (x0,y0) heading E."""
    pts = [(x0, y0)]
    y = y0
    d = 1
    for r in range(rows):
        xe = x0 + width - 1 if d == 1 else x0
        pts.append((xe, y))
        if r < rows - 1:
            y += 1
            pts.append((xe, y))
            d = -d
    return pts


def build(width=12, rows=6):
    p = Program()
    p.input_room(0, 0)
    p.room(0, 5, 6, 4)                     # rows 5..8; interior 1..4 x 6..7
    p.text(1, 6, "@>rv")
    p.text(1, 7, " ^s<")
    p.pipe([(1, 3), (1, 4)], end_direction='S')       # I -> room top col1
    pts = [(3, 9), (3, 10)] + serp_pts(3, 11, width, rows)
    last = pts[-1]
    oy = 11 + rows + 3
    p.output_room(last[0] - 1, oy)
    pts += [(last[0], oy - 1)]
    p.pipe(pts, end_direction='S')
    return p


if __name__ == '__main__':
    p = build()
    txt = p.render()
    print(txt)
    print('footprint:', p.footprint())
    print('RUN:', run(txt, '11 22 33 44', '11 22 33 44'))
