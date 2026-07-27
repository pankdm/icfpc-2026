#!/usr/bin/env python3
"""Dump every P=2 room's size and port geometry as a machine-readable table.

The floorplan problem needs the rooms as rectangles-with-ports, independent of
where build_p4 happens to put them today. This instantiates each room far apart
so nothing collides, then reports size + each port's (side, offset, direction).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'scratchpad', 'mmpar'))
from mm2lib import Grid                      # noqa: E402
import p3rooms as P3                         # noqa: E402
import prooms as P                           # noqa: E402

SPEC = [
    ('BC',    lambda g, x, y: P3.bcst(g, x, y),                 17, 11),
    ('ADMX',  lambda g, x, y: P3.admx3(g, x, y),                17, 15),
    ('BDUP',  lambda g, x, y: P3.bdup2(g, x, y),                 8, 6),
    ('MCTLA', lambda g, x, y: P3.mctl3(g, x, y, 'M', True),     11, 7),
    ('MCTLC', lambda g, x, y: P3.mctl3(g, x, y, 'K', False),    11, 7),
    ('FE1',   lambda g, x, y: P3.fe(g, x, y, '1'),              22, 21),
    ('FE2',   lambda g, x, y: P3.fe(g, x, y, '2'),              22, 21),
    ('MRG',   lambda g, x, y: P.mrg(g, x, y),                   17, 15),
]

g = Grid()
info = {}
ox = 0
for name, mk, w, h in SPEC:
    r = mk(g, ox, 0)
    ports = {}
    for pname, val in r.pipes.items():
        cell = (val[0], val[1])
        rx, ry = ox, 0
        # which wall does the attach cell sit on?
        side = None
        if cell[1] == ry:
            side = 'T'
        elif cell[1] == ry + h - 1:
            side = 'B'
        elif cell[0] == rx:
            side = 'L'
        elif cell[0] == rx + w - 1:
            side = 'R'
        off = (cell[0] - rx) if side in ('T', 'B') else (cell[1] - ry)
        ports[pname] = (side, off, val[2] if len(val) > 2 else '?')
    info[name] = dict(w=w, h=h, ports=ports)
    ox += w + 40

print(f'{"room":6s} {"w":>3s} {"h":>3s}  ports (name side offset dir)')
for name, d in info.items():
    ps = '  '.join(f'{p}:{s}@{o}:{dr}' for p, (s, o, dr) in sorted(d['ports'].items()))
    print(f'{name:6s} {d["w"]:3d} {d["h"]:3d}  {ps}')

NETS = [
    ('I.OUT', 'BC.IN'), ('BC.OA', 'ADMX.AP'), ('BC.OB', 'BDUP.BI'),
    ('BC.OH1', 'FE1.HI'), ('BC.OH2', 'FE2.HI'),
    ('ADMX.MCA', 'MCTLA.MI'), ('MCTLA.MO', 'ADMX.MA'),
    ('ADMX.MCC', 'MCTLC.MI'), ('MCTLC.MO', 'MRG.MC'),
    ('ADMX.AO1', 'FE1.DA'), ('ADMX.AO2', 'FE2.DA'),
    ('BDUP.BO1', 'FE1.DB'), ('BDUP.BO2', 'FE2.DB'),
    ('MRG.OUT', 'O.IN'),
    ('FE1.FO', 'ENG1.IN'), ('FE2.FO', 'ENG2.IN'),
    ('ENG1.OUT', 'MRG.O1'), ('ENG2.OUT', 'MRG.O2'),
]
print(f'\n{len(NETS)} nets')
deg = {}
for a, b in NETS:
    for e in (a, b):
        deg[e.split('.')[0]] = deg.get(e.split('.')[0], 0) + 1
print('room degree:', dict(sorted(deg.items(), key=lambda kv: -kv[1])))
